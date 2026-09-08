"""Persist EA config acknowledgement and activation state.

Revision ID: 0010
Revises: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_sync_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("active_config_hash", sa.String(), nullable=True),
        sa.Column("acknowledged_config_hash", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False, server_default="HOLD"),
        sa.Column("last_ack_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_config_sync_states_symbol", "config_sync_states", ["symbol"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_config_sync_states_symbol", table_name="config_sync_states")
    op.drop_table("config_sync_states")
