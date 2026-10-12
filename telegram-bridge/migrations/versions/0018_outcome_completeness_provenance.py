"""Persist authoritative outcome-history and cashflow-completeness flags.

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable, without a server default: old rows are unknown, not retroactively certified.
    op.add_column("signal_outcomes", sa.Column("outcome_history_complete", sa.Boolean(), nullable=True))
    op.add_column("signal_outcomes", sa.Column("cashflows_known", sa.Boolean(), nullable=True))
    op.add_column("signal_outcomes", sa.Column("spread_cost_known", sa.Boolean(), nullable=True))
    op.add_column("signal_outcomes", sa.Column("slippage_cost_known", sa.Boolean(), nullable=True))
    op.add_column("signal_outcomes", sa.Column("excursion_history_complete", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("signal_outcomes", "excursion_history_complete")
    op.drop_column("signal_outcomes", "slippage_cost_known")
    op.drop_column("signal_outcomes", "spread_cost_known")
    op.drop_column("signal_outcomes", "cashflows_known")
    op.drop_column("signal_outcomes", "outcome_history_complete")
