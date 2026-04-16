"""Helpers for activating Hermes runtime context per request."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from app.hermes.bridge import ensure_hermes_agent_on_path


@contextmanager
def activate_hermes_runtime(
    *,
    hermes_home_path: str,
    env: Mapping[str, str] | None = None,
    user_home_path: str | None = None,
) -> Iterator[None]:
    """Activate an isolated Hermes runtime context for one operation."""
    ensure_hermes_agent_on_path()
    from hermes_runtime import RuntimeContext, activate_runtime  # type: ignore

    runtime_ctx = RuntimeContext(
        hermes_home=Path(hermes_home_path),
        env=dict(env or {}),
        user_home=Path(user_home_path) if user_home_path else None,
    )
    with activate_runtime(runtime_ctx):
        yield

