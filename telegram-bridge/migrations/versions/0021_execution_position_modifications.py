"""Persist broker stop/target modification intent and reconciliation outcome.

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
        sa.Column("event_id", sa.String(length=160), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("broker_position_id", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("old_stop_loss", sa.Float(), nullable=False),
        sa.Column("old_take_profit", sa.Float(), nullable=False),
        sa.Column("proposed_stop_loss", sa.Float(), nullable=False),
        sa.Column("proposed_take_profit", sa.Float(), nullable=False),
        sa.Column("actual_stop_loss", sa.Float(), nullable=True),
        sa.Column("actual_take_profit", sa.Float(), nullable=True),
        sa.Column("risk_r", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("intent_evidence_ref", sa.String(length=256), nullable=False),
        sa.Column("resolution_evidence_ref", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "portfolio_key",
            "event_id",
            name="uq_execution_position_modification_event",
        ),
    )
    op.create_index(
        "ix_execution_position_modifications_pending",
        "execution_position_modifications",
        ["portfolio_key", "broker_position_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_position_modifications_pending",
        table_name="execution_position_modifications",
    )
    op.drop_table("execution_position_modifications")
