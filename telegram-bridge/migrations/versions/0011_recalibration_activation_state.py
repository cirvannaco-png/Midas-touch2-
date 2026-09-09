"""Bind configuration promotions to exact EA activation state.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "promotion_requests",
        sa.Column("config_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "promotion_requests",
        sa.Column("instrument", sa.String(), nullable=True),
    )
    op.add_column(
        "promotion_requests",
        sa.Column("timeframe", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_promotion_requests_config_hash",
        "promotion_requests",
        ["config_hash"],
    )
    op.create_index(
        "ix_promotion_requests_instrument",
        "promotion_requests",
        ["instrument"],
    )
    op.add_column(
        "config_sync_states",
        sa.Column("pending_activation_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "config_sync_states",
        sa.Column("rollback_config_hash", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("config_sync_states", "rollback_config_hash")
    op.drop_column("config_sync_states", "pending_activation_hash")
    op.drop_index(
        "ix_promotion_requests_instrument",
        table_name="promotion_requests",
    )
    op.drop_index(
        "ix_promotion_requests_config_hash",
        table_name="promotion_requests",
    )
    op.drop_column("promotion_requests", "timeframe")
    op.drop_column("promotion_requests", "instrument")
    op.drop_column("promotion_requests", "config_hash")
