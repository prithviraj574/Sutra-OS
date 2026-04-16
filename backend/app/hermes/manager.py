"""Runtime manager for cached Hermes AIAgent instances."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.hermes.bridge import ensure_hermes_agent_on_path
from app.hermes.runtime import activate_hermes_runtime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class HermesRuntimeSpec:
    """Input contract used to resolve and run a cached Hermes agent."""

    agent_id: UUID
    session_id: str
    hermes_home_path: str
    user_id: str
    env: Mapping[str, str] = field(default_factory=dict)
    model: str = ""
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    user_home_path: str | None = None
    skip_context_files: bool = True
    skip_memory: bool = False


@dataclass
class CachedAgentRuntime:
    agent: Any
    session_db: Any
    fingerprint: str
    last_used_at: datetime


def _default_session_db_factory():
    ensure_hermes_agent_on_path()
    from hermes_state import SessionDB  # type: ignore

    return SessionDB()


def _default_ai_agent_factory(**kwargs):
    from app.hermes import AIAgent

    return AIAgent(**kwargs)


class HermesRuntimeManager:
    """Caches AIAgent instances by `(agent_id, session_id)` with safe invalidation."""

    def __init__(
        self,
        *,
        idle_ttl_seconds: int = 1800,
        max_cached_agents: int = 256,
        ai_agent_factory: Callable[..., Any] | None = None,
        session_db_factory: Callable[[], Any] | None = None,
        runtime_activator: Callable[[HermesRuntimeSpec], AbstractContextManager] | None = None,
    ):
        self._idle_ttl = timedelta(seconds=max(idle_ttl_seconds, 30))
        self._max_cached_agents = max(max_cached_agents, 1)
        self._ai_agent_factory = ai_agent_factory or _default_ai_agent_factory
        self._session_db_factory = session_db_factory or _default_session_db_factory
        self._runtime_activator = runtime_activator or self._activate_runtime

        self._cache: dict[tuple[UUID, str], CachedAgentRuntime] = {}
        self._agent_locks: dict[UUID, threading.Lock] = {}
        self._cache_lock = threading.Lock()

    @staticmethod
    def _cache_key(spec: HermesRuntimeSpec) -> tuple[UUID, str]:
        return spec.agent_id, spec.session_id

    @staticmethod
    def _fingerprint(spec: HermesRuntimeSpec) -> str:
        payload = {
            "agent_id": str(spec.agent_id),
            "session_id": spec.session_id,
            "hermes_home_path": spec.hermes_home_path,
            "user_id": spec.user_id,
            "model": spec.model,
            "provider": spec.provider,
            "base_url": spec.base_url,
            "api_key": spec.api_key,
            "user_home_path": spec.user_home_path,
            "skip_context_files": spec.skip_context_files,
            "skip_memory": spec.skip_memory,
            "env": sorted((str(k), str(v)) for k, v in spec.env.items()),
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _close_runtime(runtime: CachedAgentRuntime) -> None:
        try:
            close_fn = getattr(runtime.session_db, "close", None)
            if callable(close_fn):
                close_fn()
        except Exception:
            pass

    def _activate_runtime(self, spec: HermesRuntimeSpec):
        return activate_hermes_runtime(
            hermes_home_path=spec.hermes_home_path,
            env=spec.env,
            user_home_path=spec.user_home_path,
        )

    def _evict_idle_locked(self, now: datetime) -> None:
        if not self._cache:
            return

        stale_keys = [
            key for key, value in self._cache.items()
            if now - value.last_used_at > self._idle_ttl
        ]
        for key in stale_keys:
            stale = self._cache.pop(key, None)
            if stale is not None:
                self._close_runtime(stale)

        if len(self._cache) <= self._max_cached_agents:
            return

        # Drop oldest entries until cache is back under limit.
        ordered = sorted(self._cache.items(), key=lambda item: item[1].last_used_at)
        over_by = len(self._cache) - self._max_cached_agents
        for key, _ in ordered[:over_by]:
            stale = self._cache.pop(key, None)
            if stale is not None:
                self._close_runtime(stale)

    def _get_agent_lock(self, agent_id: UUID) -> threading.Lock:
        with self._cache_lock:
            lock = self._agent_locks.get(agent_id)
            if lock is None:
                lock = threading.Lock()
                self._agent_locks[agent_id] = lock
            return lock

    def _build_runtime(self, spec: HermesRuntimeSpec, fingerprint: str) -> CachedAgentRuntime:
        kwargs: dict[str, Any] = {
            "session_id": spec.session_id,
            "session_db": None,
            "user_id": spec.user_id,
            "quiet_mode": True,
            "platform": "sutra-backend",
            "skip_context_files": spec.skip_context_files,
            "skip_memory": spec.skip_memory,
            "pass_session_id": True,
        }
        if spec.model:
            kwargs["model"] = spec.model
        if spec.provider:
            kwargs["provider"] = spec.provider
        if spec.base_url:
            kwargs["base_url"] = spec.base_url
        if spec.api_key:
            kwargs["api_key"] = spec.api_key

        with self._runtime_activator(spec):
            session_db = self._session_db_factory()
            kwargs["session_db"] = session_db
            agent = self._ai_agent_factory(**kwargs)

        return CachedAgentRuntime(
            agent=agent,
            session_db=session_db,
            fingerprint=fingerprint,
            last_used_at=_utc_now(),
        )

    def _get_or_create_runtime(self, spec: HermesRuntimeSpec) -> CachedAgentRuntime:
        if not spec.session_id.strip():
            raise ValueError("session_id cannot be empty")

        key = self._cache_key(spec)
        fingerprint = self._fingerprint(spec)
        now = _utc_now()
        stale: CachedAgentRuntime | None = None

        with self._cache_lock:
            self._evict_idle_locked(now)
            cached = self._cache.get(key)
            if cached is not None and cached.fingerprint == fingerprint:
                cached.last_used_at = now
                return cached
            stale = cached

        fresh = self._build_runtime(spec, fingerprint)

        with self._cache_lock:
            existing = self._cache.get(key)
            if existing is not None and existing.fingerprint == fingerprint:
                existing.last_used_at = now
                self._close_runtime(fresh)
                if stale is not None and stale is not existing:
                    self._close_runtime(stale)
                return existing

            self._cache[key] = fresh
            self._evict_idle_locked(now)

        if stale is not None:
            self._close_runtime(stale)
        return fresh

    def run_turn(
        self,
        *,
        spec: HermesRuntimeSpec,
        user_message: str,
        persist_user_message: str | None = None,
    ) -> dict[str, Any]:
        trimmed_message = user_message.strip()
        if not trimmed_message:
            raise ValueError("Message cannot be empty")

        agent_lock = self._get_agent_lock(spec.agent_id)
        with agent_lock:
            runtime = self._get_or_create_runtime(spec)
            with self._runtime_activator(spec):
                history = runtime.session_db.get_messages_as_conversation(spec.session_id)
                result = runtime.agent.run_conversation(
                    user_message=trimmed_message,
                    conversation_history=history,
                    persist_user_message=persist_user_message or trimmed_message,
                )
            runtime.last_used_at = _utc_now()
            return result

    def close(self) -> None:
        with self._cache_lock:
            runtimes = list(self._cache.values())
            self._cache.clear()
            self._agent_locks.clear()
        for runtime in runtimes:
            self._close_runtime(runtime)

