"""Runtime validation for deployment-sensitive paths."""

from __future__ import annotations

import os

from app.core.settings import Settings


def validate_runtime_environment(settings: Settings) -> None:
    homes_root = settings.hermes_homes_root

    if settings.hermes_homes_root_is_configured:
        if not homes_root.exists():
            raise RuntimeError(
                f"SUTRA_HERMES_HOMES_ROOT does not exist: {homes_root}. "
                "On Cloud Run this usually means the Filestore mount is missing."
            )
        if not homes_root.is_dir():
            raise RuntimeError(
                f"SUTRA_HERMES_HOMES_ROOT is not a directory: {homes_root}."
            )
        if not os.access(homes_root, os.R_OK | os.W_OK | os.X_OK):
            raise RuntimeError(
                f"SUTRA_HERMES_HOMES_ROOT is not readable/writable: {homes_root}."
            )
        return

    homes_root.mkdir(parents=True, exist_ok=True)
