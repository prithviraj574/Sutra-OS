"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.runtime import validate_runtime_environment
from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    validate_runtime_environment(settings)
    app = FastAPI(title="Sutra Backend", version="0.1.0")

    allowed_origins = ["*"]
    if settings.frontend_url:
        allowed_origins = [settings.frontend_url]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
