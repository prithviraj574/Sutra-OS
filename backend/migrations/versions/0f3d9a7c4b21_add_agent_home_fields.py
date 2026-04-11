"""add agent home fields

Revision ID: 0f3d9a7c4b21
Revises: 71afe56038b5
Create Date: 2026-04-11 15:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0f3d9a7c4b21"
down_revision: Union[str, Sequence[str], None] = "71afe56038b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("agent", sa.Column("hermes_home_path", sa.String(), nullable=True))
    op.add_column("agent", sa.Column("workspace_key", sa.String(), nullable=True))
    op.create_index(op.f("ix_agent_workspace_key"), "agent", ["workspace_key"], unique=False)

    op.execute("UPDATE agent SET hermes_home_path = '' WHERE hermes_home_path IS NULL")
    op.execute("UPDATE agent SET workspace_key = '' WHERE workspace_key IS NULL")

    op.alter_column("agent", "hermes_home_path", nullable=False)
    op.alter_column("agent", "workspace_key", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_agent_workspace_key"), table_name="agent")
    op.drop_column("agent", "workspace_key")
    op.drop_column("agent", "hermes_home_path")
