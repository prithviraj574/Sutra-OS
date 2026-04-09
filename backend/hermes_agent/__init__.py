"""Backward-compatible shim for old import paths."""

from backend.app.hermes import ensure_hermes_agent_on_path

__all__ = ["AIAgent", "ensure_hermes_agent_on_path"]


def __getattr__(name: str):
    if name != "AIAgent":
        raise AttributeError(name)

    from backend.app.hermes import __getattr__ as _hermes_getattr

    return _hermes_getattr(name)
