from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_runtime.db import create_engine_and_sessionmaker, init_db
from agent_runtime.store import AgentStore
from api.agents import router as agent_router
from config import Config, get_config


def create_app(config: Config | None = None) -> FastAPI:
    config = config or get_config()
    engine, sessionmaker = create_engine_and_sessionmaker(config.app.postgres_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="Agent Runtime", lifespan=lifespan)
    app.state.engine = engine
    app.state.config = config
    app.state.store = AgentStore(sessionmaker)
    app.include_router(agent_router)
    return app
