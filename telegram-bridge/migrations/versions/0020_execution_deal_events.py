"""Persist idempotent broker deal events for partial-close/restart recovery.

Revision ID: 0020
Revises: 0019
"""
import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_deal_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("portfolio_key", sa.String(), nullable=False),
        sa.Column("broker_deal_id", sa.String(), nullable=False),
        sa.Column("broker_order_id", sa.String(), nullable=True),
        sa.Column("broker_position_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("deal_type", sa.String(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("profit_cashflow", sa.Float(), nullable=False),
        sa.Column("commission_cashflow", sa.Float(), nullable=False),
        sa.Column("swap_cashflow", sa.Float(), nullable=False),
        sa.Column("fee_cashflow", sa.Float(), nullable=False),
        sa.Column("cashflows_known", sa.Boolean(), nullable=False),
        sa.Column("event_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "portfolio_key",
            "broker_deal_id",
            name="uq_execution_deal_portfolio_deal",
        ),
    )
    op.create_index(
        "ix_execution_deal_events_position",
        "execution_deal_events",
        ["portfolio_key", "broker_position_id"],
    )
    op.create_index(
        "ix_execution_deal_events_order",
        "execution_deal_events",
        ["portfolio_key", "broker_order_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_deal_events_order", table_name="execution_deal_events")
    op.drop_index("ix_execution_deal_events_position", table_name="execution_deal_events")
    op.drop_table("execution_deal_events")
