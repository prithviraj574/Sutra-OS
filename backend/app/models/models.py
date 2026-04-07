from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, MetaData, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.enums import AgentRuntimeState

SQLModel.metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ModelBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        nullable=False,
    )


class User(ModelBase, table=True):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("firebase_uid", name="uq_user_firebase_uid"),
        UniqueConstraint("email", name="uq_user_email"),
    )

    firebase_uid: str = Field(index=True, nullable=False)
    email: str = Field(index=True, nullable=False)
    name: str | None = Field(default=None)


class Agent(ModelBase, table=True):
    __tablename__ = "agent"

    user_id: UUID = Field(foreign_key="user.id", index=True, nullable=False)
    name: str = Field(nullable=False)


class AgentRuntime(ModelBase, table=True):
    __tablename__ = "agent_runtime"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_agent_runtime_agent_id"),
    )

    agent_id: UUID = Field(foreign_key="agent.id", index=True, nullable=False)
    state: str = Field(default=AgentRuntimeState.STOPPED.value, nullable=False)
    pd_name: str | None = Field(default=None, index=True)
    host_instance_name: str | None = Field(default=None)
    firecracker_id: str | None = Field(default=None)
    guest_ip: str | None = Field(default=None)
    booted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    last_seen_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    last_error: str | None = Field(default=None)
