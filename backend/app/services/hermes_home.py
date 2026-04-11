"""Provision Hermes-compatible homes for hosted agents.

This remains a service even when we reuse Hermes conventions because the hosted
app needs an adapter boundary:

- Hermes CLI profile creation is HOME-anchored (`~/.hermes/profiles/<name>`)
- our backend needs arbitrary NFS-backed target paths per agent
- we want a narrow place to reuse Hermes-safe defaults without importing broad
  runtime code into request handlers
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.hermes.bridge import ensure_hermes_agent_on_path
from app.core.settings import Settings

_FALLBACK_PROFILE_DIRS = (
    "memories",
    "sessions",
    "skills",
    "skins",
    "logs",
    "plans",
    "workspace",
    "cron",
)


def _resolve_profile_dirs() -> tuple[str, ...]:
    """Prefer Hermes' own profile bootstrap directories when importable.

    We do not call `create_profile()` directly because Hermes' CLI profile
    helpers are intentionally HOME-anchored and bundled with wrapper/alias
    concerns that do not fit the hosted backend.
    """
    try:
        ensure_hermes_agent_on_path()
        from hermes_cli.profiles import _PROFILE_DIRS  # type: ignore

        if isinstance(_PROFILE_DIRS, (list, tuple)) and _PROFILE_DIRS:
            return tuple(str(item) for item in _PROFILE_DIRS)
    except Exception:
        pass
    return _FALLBACK_PROFILE_DIRS


PROFILE_DIRS = _resolve_profile_dirs()


class ProvisionHermesHomeService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def build_home_path(self, user_id: UUID, agent_id: UUID) -> Path:
        del user_id
        return (
            self._settings.hermes_homes_root
            / ".hermes"
            / "profiles"
            / f"agent-{agent_id}"
        )

    def provision(self, home_path: Path, agent_name: str) -> None:
        home_path.mkdir(parents=True, exist_ok=True)
        for subdir in PROFILE_DIRS:
            (home_path / subdir).mkdir(parents=True, exist_ok=True)

        self._write_if_missing(
            home_path / "SOUL.md",
            self._default_soul(agent_name),
        )
        self._write_if_missing(
            home_path / "memories" / "USER.md",
            "# User\n\nThis file can hold stable user-specific context.\n",
        )
        self._write_if_missing(
            home_path / "memories" / "MEMORY.md",
            "# Memory\n\nThis file can hold durable working memory.\n",
        )

    @staticmethod
    def _write_if_missing(path: Path, content: str) -> None:
        if path.exists():
            return
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _default_soul(agent_name: str) -> str:
        return (
            f"# {agent_name}\n\n"
            "You are a helpful AI agent operating on behalf of your user.\n"
            "Be clear, capable, and careful with their context and files.\n"
        )
