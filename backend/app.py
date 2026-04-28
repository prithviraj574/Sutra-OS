from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_runtime.store import AgentStore
from api.agents import router as agent_router
from api.config import router as config_router
from config import Config, get_config
from database import create_engine_and_sessionmaker, init_db


def create_app(config: Config | None = None) -> FastAPI:
    config = config or get_config()
    engine, sessionmaker = create_engine_and_sessionmaker(config.app.postgres_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="Agent Runtime", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.app.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.engine = engine
    app.state.config = config
    app.state.store = AgentStore(sessionmaker)
    app.include_router(agent_router)
    app.include_router(config_router)
    return app
