"""Persist temporal outcome provenance and execution costs.

Revision ID: 0014
Revises: 0013

This migration follows the already-applied environment strategy outcome
migration. It deliberately does not re-add strategy/environment columns from
0013; it only adds the provenance/cost fields that were previously introduced
on a competing 0013 head.
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signal_outcomes", sa.Column("signal_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("signal_outcomes", sa.Column("resolution", sa.String(64), nullable=True))
    op.add_column("signal_outcomes", sa.Column("commission_cost", sa.Float(), nullable=True))
    op.add_column("signal_outcomes", sa.Column("spread_cost", sa.Float(), nullable=True))
    op.add_column("signal_outcomes", sa.Column("slippage_cost", sa.Float(), nullable=True))
    op.create_index("ix_signal_outcomes_signal_time", "signal_outcomes", ["signal_time"])
    op.create_index("ix_signal_outcomes_resolution", "signal_outcomes", ["resolution"])
    op.create_index("ix_signal_outcomes_symbol_strategy", "signal_outcomes", ["symbol", "strategy"])


def downgrade() -> None:
    op.drop_index("ix_signal_outcomes_symbol_strategy", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_resolution", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_signal_time", table_name="signal_outcomes")
    op.drop_column("signal_outcomes", "slippage_cost")
    op.drop_column("signal_outcomes", "spread_cost")
    op.drop_column("signal_outcomes", "commission_cost")
    op.drop_column("signal_outcomes", "resolution")
    op.drop_column("signal_outcomes", "signal_time")
