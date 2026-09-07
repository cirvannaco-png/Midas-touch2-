"""subscribers + payments tables (copy-trading entitlement, payments)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-04

Adds the two tables backing app/subscriptions.py, app/payments_bot.py,
app/copy_trading.py and app/group_enforcement.py: who's a paying
subscriber (subscribers), and the Telegram Payments transactions that
funded their entitlement (payments).

Plain String status columns, no PG_ENUM — same call as
promotion_requests.status in 0006 and bot_settings before it, for the
exact CREATE TYPE / DuplicateObjectError reason documented on
app/models.py's _signal_status_type.
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscribers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_user_id", sa.String(), nullable=False, unique=True),
        sa.Column("telegram_username", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("copy_feed_api_key", sa.String(), nullable=True, unique=True),
        sa.Column("warned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_subscribers_telegram_user_id ON subscribers (telegram_user_id);"
    ))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscribers_status ON subscribers (status);"))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_subscribers_copy_feed_api_key ON subscribers (copy_feed_api_key);"
    ))

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_payment_charge_id", sa.String(), nullable=False, unique=True),
        sa.Column("subscriber_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("invoice_payload", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="succeeded"),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_payments_telegram_payment_charge_id "
        "ON payments (telegram_payment_charge_id);"
    ))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_payments_subscriber_id ON payments (subscriber_id);"))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS payments;"))
    op.execute(sa.text("DROP TABLE IF EXISTS subscribers;"))
