"""add chat thread table

Revision ID: b19c6f5a2c0d
Revises: 0f3d9a7c4b21
Create Date: 2026-04-11 23:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b19c6f5a2c0d"
down_revision: Union[str, Sequence[str], None] = "0f3d9a7c4b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "chat_thread",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("hermes_session_id", sa.String(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"], name=op.f("fk_chat_thread_agent_id_agent")),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name=op.f("fk_chat_thread_user_id_user")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_thread")),
        sa.UniqueConstraint("hermes_session_id", name="uq_chat_thread_hermes_session_id"),
    )
    op.create_index(op.f("ix_chat_thread_agent_id"), "chat_thread", ["agent_id"], unique=False)
    op.create_index(op.f("ix_chat_thread_user_id"), "chat_thread", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_chat_thread_user_id"), table_name="chat_thread")
    op.drop_index(op.f("ix_chat_thread_agent_id"), table_name="chat_thread")
    op.drop_table("chat_thread")

