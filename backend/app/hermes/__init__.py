"""Hermes integration boundary for backend services."""

from .bridge import ensure_hermes_agent_on_path

__all__ = ["AIAgent", "ensure_hermes_agent_on_path"]


def __getattr__(name: str):
    if name != "AIAgent":
        raise AttributeError(name)

    from .bridge import __getattr__ as _bridge_getattr

    return _bridge_getattr(name)
