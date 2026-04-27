from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_runtime.db import create_engine_and_sessionmaker, init_db
from agent_runtime.repository import AgentRepository
from agent_runtime.settings import Settings, get_settings
from api.agents import router as agent_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine, sessionmaker = create_engine_and_sessionmaker(settings.postgres_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="Agent Runtime", lifespan=lifespan)
    app.state.engine = engine
    app.state.settings = settings
    app.state.repository = AgentRepository(sessionmaker)
    app.include_router(agent_router)
    return app
