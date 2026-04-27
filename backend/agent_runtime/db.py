from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    agents: Mapped[list[Agent]] = relationship(back_populates="user")
    sessions: Mapped[list[AgentSession]] = relationship(back_populates="user")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), default="Default agent")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    tools: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship(back_populates="agents")
    sessions: Mapped[list[AgentSession]] = relationship(back_populates="agent")


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True, default="default")
    status: Mapped[str] = mapped_column(String(32), default="active")
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship(back_populates="sessions")
    agent: Mapped[Agent] = relationship(back_populates="sessions")


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
            text("ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS messages JSONB DEFAULT '[]'::jsonb")
        )
        await conn.execute(
            text(
                "ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS updated_at "
                "TIMESTAMP WITH TIME ZONE DEFAULT now()"
            )
        )
        await conn.execute(text("ALTER TABLE agent_sessions ALTER COLUMN system_prompt DROP NOT NULL"))
        await conn.execute(text("ALTER TABLE agent_sessions ALTER COLUMN model DROP NOT NULL"))
