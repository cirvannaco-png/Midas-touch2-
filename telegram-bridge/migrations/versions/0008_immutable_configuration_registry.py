"""Immutable candidate configuration registry.

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configuration_registry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("strategy", sa.String(), nullable=False),
        sa.Column("instrument", sa.String(), nullable=False),
        sa.Column("timeframe", sa.String(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("data_version", sa.String(), nullable=False),
        sa.Column("optimizer_version", sa.String(), nullable=False),
        sa.Column("train_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("train_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("holdout_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("holdout_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("performance_metrics", sa.JSON(), nullable=True),
        sa.Column("risk_metrics", sa.JSON(), nullable=False),
        sa.Column("regime_conditions", sa.JSON(), nullable=True),
        sa.Column("lifecycle_status", sa.String(), nullable=False, server_default="OPTIMIZED"),
        sa.Column("provenance", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("config_hash", name="uq_configuration_registry_config_hash"),
    )
    op.create_index("ix_configuration_registry_strategy_instrument_timeframe", "configuration_registry", ["strategy", "instrument", "timeframe"])
    op.create_index("ix_configuration_registry_lifecycle_status", "configuration_registry", ["lifecycle_status"])


def downgrade() -> None:
    op.drop_index("ix_configuration_registry_lifecycle_status", table_name="configuration_registry")
    op.drop_index("ix_configuration_registry_strategy_instrument_timeframe", table_name="configuration_registry")
    op.drop_table("configuration_registry")
