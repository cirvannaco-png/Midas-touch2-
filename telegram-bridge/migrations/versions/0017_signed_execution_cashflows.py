"""Persist signed broker cashflows alongside positive execution cost magnitudes.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signal_outcomes", sa.Column("commission_cashflow", sa.Float(), nullable=True))
    op.add_column("signal_outcomes", sa.Column("swap_cashflow", sa.Float(), nullable=True))
    op.add_column("signal_outcomes", sa.Column("broker_fee_cashflow", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("signal_outcomes", "broker_fee_cashflow")
    op.drop_column("signal_outcomes", "swap_cashflow")
    op.drop_column("signal_outcomes", "commission_cashflow")
