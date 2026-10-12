"""Restore durable research, execution-ledger, and portfolio-reservation schema.

This is an additive compatibility migration. Midas-specific configuration,
decision-provenance, and signal-outbox migrations remain unchanged.

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
    op.create_table(
        "research_experiments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code_sha", sa.String(), nullable=False),
        sa.Column("config_hash", sa.String(), nullable=False),
        sa.Column("data_snapshot", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("train_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("train_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("oos_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("oos_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("walk_forward_id", sa.String(), nullable=True),
        sa.Column("holdout_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_research_experiments_experiment_id", "research_experiments", ["experiment_id"], unique=True)
    op.create_index("ix_research_experiments_config_hash", "research_experiments", ["config_hash"])
    op.create_index("ix_research_experiments_walk_forward_id", "research_experiments", ["walk_forward_id"])

    op.create_table(
        "experiment_observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(), nullable=False),
        sa.Column("signal_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(), nullable=False),
    )
    op.create_index("ix_experiment_observations_experiment_id", "experiment_observations", ["experiment_id"])
    op.create_index("ix_exp_obs_experiment_time", "experiment_observations", ["experiment_id", "timestamp"])
    op.create_index("ix_exp_obs_signal", "experiment_observations", ["signal_id"])
    op.create_index("ix_experiment_observations_fingerprint", "experiment_observations", ["fingerprint"])

    op.create_table(
        "experiment_book_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(), nullable=False),
        sa.Column("signal_id", sa.String(), nullable=False),
        sa.Column("book", sa.String(), nullable=False),
        sa.Column("strategy", sa.String(), nullable=True),
        sa.Column("direction", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("realized_r", sa.Float(), nullable=True),
        sa.Column("mfe_r", sa.Float(), nullable=True),
        sa.Column("mae_r", sa.Float(), nullable=True),
        sa.Column("hypothetical", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_experiment_book_results_experiment_id", "experiment_book_results", ["experiment_id"])
    op.create_index("ix_experiment_book_results_signal_id", "experiment_book_results", ["signal_id"])
    op.create_index("ix_book_experiment_book", "experiment_book_results", ["experiment_id", "book"])

    op.create_table(
        "validation_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(), nullable=False),
        sa.Column("validation_type", sa.String(), nullable=False),
        sa.Column("window_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_validation_runs_experiment_id", "validation_runs", ["experiment_id"])

    op.create_table(
        "promotion_decision_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(), nullable=False),
        sa.Column("champion_id", sa.String(), nullable=False),
        sa.Column("challenger_id", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("holdout_passed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_promotion_decision_audit_experiment_id", "promotion_decision_audit", ["experiment_id"])

    op.create_table(
        "execution_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("signal_id", sa.String(), nullable=True),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("broker_order_id", sa.String(), nullable=True),
        sa.Column("broker_deal_id", sa.String(), nullable=True),
        sa.Column("broker_position_id", sa.String(), nullable=True),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
    )
    op.create_index("ix_execution_ledger_request_id", "execution_ledger", ["request_id"], unique=True)
    op.create_index("ix_exec_ledger_state", "execution_ledger", ["state"])
    op.create_index("ix_execution_ledger_signal_id", "execution_ledger", ["signal_id"])

    op.create_table(
        "portfolio_reservations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("risk_r", sa.Float(), nullable=False),
        sa.Column("volatility", sa.Float(), nullable=False),
        sa.Column("factor_exposure", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_portfolio_reservations_request_id", "portfolio_reservations", ["request_id"], unique=True)
    op.create_index("ix_portfolio_reservations_status", "portfolio_reservations", ["status"])


def downgrade() -> None:
    # Downgrade removes only tables introduced by this revision.
    op.drop_index("ix_portfolio_reservations_status", table_name="portfolio_reservations")
    op.drop_index("ix_portfolio_reservations_request_id", table_name="portfolio_reservations")
    op.drop_table("portfolio_reservations")

    op.drop_index("ix_execution_ledger_signal_id", table_name="execution_ledger")
    op.drop_index("ix_exec_ledger_state", table_name="execution_ledger")
    op.drop_index("ix_execution_ledger_request_id", table_name="execution_ledger")
    op.drop_table("execution_ledger")

    op.drop_index("ix_promotion_decision_audit_experiment_id", table_name="promotion_decision_audit")
    op.drop_table("promotion_decision_audit")

    op.drop_index("ix_validation_runs_experiment_id", table_name="validation_runs")
    op.drop_table("validation_runs")

    op.drop_index("ix_book_experiment_book", table_name="experiment_book_results")
    op.drop_index("ix_experiment_book_results_signal_id", table_name="experiment_book_results")
    op.drop_index("ix_experiment_book_results_experiment_id", table_name="experiment_book_results")
    op.drop_table("experiment_book_results")

    op.drop_index("ix_experiment_observations_fingerprint", table_name="experiment_observations")
    op.drop_index("ix_exp_obs_signal", table_name="experiment_observations")
    op.drop_index("ix_exp_obs_experiment_time", table_name="experiment_observations")
    op.drop_index("ix_experiment_observations_experiment_id", table_name="experiment_observations")
    op.drop_table("experiment_observations")

    op.drop_index("ix_research_experiments_walk_forward_id", table_name="research_experiments")
    op.drop_index("ix_research_experiments_config_hash", table_name="research_experiments")
    op.drop_index("ix_research_experiments_experiment_id", table_name="research_experiments")
    op.drop_table("research_experiments")
