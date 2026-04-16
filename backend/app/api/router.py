"""Top-level API router composition."""

from fastapi import APIRouter

from app.api.routes.agents import router as agents_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.me import router as me_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(me_router)
router.include_router(agents_router)
router.include_router(chat_router)
