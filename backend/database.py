from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from models import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def normalize_postgres_url(url: str) -> tuple[str, dict[str, Any]]:
    if url.startswith("postgresql+asyncpg://"):
        normalized = url
    elif url.startswith("postgresql://"):
        normalized = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    else:
        normalized = url

    parsed = make_url(normalized)
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    connect_args: dict[str, Any] = {}
    if sslmode in {"require", "verify-ca", "verify-full"}:
        connect_args["ssl"] = True
    return parsed.set(query=query).render_as_string(hide_password=False), connect_args


def create_engine_and_sessionmaker(postgres_url: str) -> tuple[AsyncEngine, async_sessionmaker]:
    url, connect_args = normalize_postgres_url(postgres_url)
    engine = create_async_engine(url, connect_args=connect_args, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS agent_id VARCHAR(64)"))
        await conn.execute(
            text("ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'active'")
        )
        await conn.execute(
            text("ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS system_prompt TEXT DEFAULT ''")
        )
        await conn.execute(
            text("ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS model JSONB DEFAULT '{}'::jsonb")
        )
        await conn.execute(
            text("ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS tools JSONB DEFAULT '[]'::jsonb")
        )
        await conn.execute(
            text("ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS messages JSONB DEFAULT '[]'::jsonb")
        )
        await conn.execute(
            text(
                "ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS updated_at "
                "TIMESTAMP WITH TIME ZONE DEFAULT now()"
            )
        )
        for table_name, column_name in [
            ("agent_sessions", "system_prompt"),
            ("agent_sessions", "model"),
            ("agent_sessions", "tenant_id"),
            ("agents", "system_prompt"),
            ("agents", "model"),
            ("agents", "tools"),
        ]:
            exists = await conn.scalar(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = :table_name
                          AND column_name = :column_name
                    )
                    """
                ),
                {"table_name": table_name, "column_name": column_name},
            )
            if exists:
                await conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP NOT NULL"))
