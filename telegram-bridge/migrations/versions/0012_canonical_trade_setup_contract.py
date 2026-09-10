"""Persist the complete canonical TradeSetup target contract.

Revision ID: 0012
Revises: 0011

The bridge must preserve strategy thesis invalidation separately from the
protective stop and must not silently discard the final target. Both fields
are nullable for backward compatibility with older EA payloads; the
execution/copy gates can require them once the EA publisher is upgraded.
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("invalidation", sa.Float(), nullable=True))
    op.add_column("signals", sa.Column("final_tp", sa.Float(), nullable=True))
    op.add_column("signals", sa.Column("strategy", sa.String(64), nullable=True))
    op.create_index("ix_signals_strategy", "signals", ["strategy"])


def downgrade() -> None:
    op.drop_index("ix_signals_strategy", table_name="signals")
    op.drop_column("signals", "strategy")
    op.drop_column("signals", "final_tp")
    op.drop_column("signals", "invalidation")
