"""Import bridge for the local `hermes-agent` submodule."""

from pathlib import Path
import sys


def ensure_hermes_agent_on_path() -> Path:
    """Add the local `hermes-agent` repository path to `sys.path`."""
    repo_root = Path(__file__).resolve().parents[3]
    hermes_repo = repo_root / "hermes-agent"
    if not hermes_repo.exists():
        raise RuntimeError(f"hermes-agent directory not found at: {hermes_repo}")

    hermes_repo_str = str(hermes_repo)
    if hermes_repo_str not in sys.path:
        sys.path.insert(0, hermes_repo_str)
    return hermes_repo


def __getattr__(name: str):
    if name != "AIAgent":
        raise AttributeError(name)

    ensure_hermes_agent_on_path()
    try:
        from run_agent import AIAgent  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local hermes deps
        raise RuntimeError(
            "Failed to import AIAgent from local hermes-agent submodule. "
            "Install hermes-agent dependencies and retry."
        ) from exc
    return AIAgent


__all__ = ["AIAgent", "ensure_hermes_agent_on_path"]

