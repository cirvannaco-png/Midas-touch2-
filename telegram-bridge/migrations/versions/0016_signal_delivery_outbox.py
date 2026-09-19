"""Durable signal delivery outbox for latency isolation.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_delivery_outbox",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_signal_delivery_outbox_signal_id", "signal_delivery_outbox", ["signal_id"], unique=True)
    op.create_index("ix_signal_delivery_outbox_status_next_attempt", "signal_delivery_outbox", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_signal_delivery_outbox_status_next_attempt", table_name="signal_delivery_outbox")
    op.drop_index("ix_signal_delivery_outbox_signal_id", table_name="signal_delivery_outbox")
    op.drop_table("signal_delivery_outbox")
