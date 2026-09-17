"""Persist environment/strategy context with resolved signal outcomes.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signal_outcomes", sa.Column("strategy", sa.String(64), nullable=True))
    op.add_column("signal_outcomes", sa.Column("environment_key", sa.String(512), nullable=True))
    op.add_column("signal_outcomes", sa.Column("environment", sa.JSON(), nullable=True))
    op.add_column("signal_outcomes", sa.Column("exit_reason", sa.String(64), nullable=True))
    op.create_index("ix_signal_outcomes_strategy", "signal_outcomes", ["strategy"])
    op.create_index("ix_signal_outcomes_environment_key", "signal_outcomes", ["environment_key"])


def downgrade() -> None:
    op.drop_index("ix_signal_outcomes_environment_key", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_strategy", table_name="signal_outcomes")
    op.drop_column("signal_outcomes", "exit_reason")
    op.drop_column("signal_outcomes", "environment")
    op.drop_column("signal_outcomes", "environment_key")
    op.drop_column("signal_outcomes", "strategy")
