"""Scope execution records and risk reservations to an account portfolio.

Revision ID: 0018
Revises: 0017
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_ledger",
        sa.Column("portfolio_key", sa.String(), nullable=True),
    )
    op.add_column(
        "portfolio_reservations",
        sa.Column("portfolio_key", sa.String(), nullable=True),
    )
    # Existing records predate scoped admission. Preserve them in a distinct
    # legacy bucket instead of silently attributing them to an active account.
    op.execute(
        "UPDATE execution_ledger SET portfolio_key = 'legacy-unscoped' WHERE portfolio_key IS NULL"
    )
    op.execute(
        "UPDATE portfolio_reservations SET portfolio_key = 'legacy-unscoped' WHERE portfolio_key IS NULL"
    )
    op.alter_column(
        "execution_ledger",
        "portfolio_key",
        existing_type=sa.String(),
        nullable=False,
        server_default=sa.text("'legacy-unscoped'"),
    )
    op.alter_column(
        "portfolio_reservations",
        "portfolio_key",
        existing_type=sa.String(),
        nullable=False,
        server_default=sa.text("'legacy-unscoped'"),
    )
    op.create_index("ix_execution_ledger_portfolio_key", "execution_ledger", ["portfolio_key"])
    op.create_index("ix_portfolio_reservations_portfolio_key", "portfolio_reservations", ["portfolio_key"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_reservations_portfolio_key", table_name="portfolio_reservations")
    op.drop_index("ix_execution_ledger_portfolio_key", table_name="execution_ledger")
    op.drop_column("portfolio_reservations", "portfolio_key")
    op.drop_column("execution_ledger", "portfolio_key")
