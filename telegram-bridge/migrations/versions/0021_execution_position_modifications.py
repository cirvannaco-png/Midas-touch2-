"""Persist immutable broker-confirmed position modification events.

Revision ID: 0021
Revises: 0020
"""
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_position_modifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("portfolio_key", sa.String(), nullable=False),
        sa.Column("broker_position_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("previous_sl", sa.Float(), nullable=False),
        sa.Column("applied_sl", sa.Float(), nullable=False),
        sa.Column("previous_tp", sa.Float(), nullable=False),
        sa.Column("applied_tp", sa.Float(), nullable=False),
        sa.Column("risk_r", sa.Float(), nullable=False),
        sa.Column("volatility", sa.Float(), nullable=False),
        sa.Column("evidence_ref", sa.String(length=256), nullable=False),
        sa.Column("event_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "portfolio_key",
            "evidence_ref",
            name="uq_execution_position_mod_portfolio_evidence",
        ),
    )
    op.create_index(
        "ix_execution_position_modifications_position",
        "execution_position_modifications",
        ["portfolio_key", "broker_position_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_position_modifications_position",
        table_name="execution_position_modifications",
    )
    op.drop_table("execution_position_modifications")
