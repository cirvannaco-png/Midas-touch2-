from pathlib import Path

import app.config_evaluation_model
import app.config_registry_model
import app.config_sync_state_model
from app import models
from app.database import Base


def test_restored_research_and_execution_tables_are_registered():
    expected = {
        "research_experiments",
        "experiment_observations",
        "experiment_book_results",
        "validation_runs",
        "promotion_decision_audit",
        "execution_ledger",
        "portfolio_reservations",
    }
    assert expected.issubset(Base.metadata.tables)


def test_execution_ledger_has_idempotency_and_reconciliation_fields():
    table = Base.metadata.tables["execution_ledger"]
    assert {"request_id", "signal_id", "state", "request_json", "result_json",
            "broker_order_id", "broker_deal_id", "broker_position_id",
            "checked_at", "sent_at", "reconciled_at", "lease_until",
            "latency_ms"}.issubset(table.columns.keys())
    request_id = table.columns["request_id"]
    assert request_id.unique is True
    assert request_id.nullable is False


def test_portfolio_reservations_preserve_risk_and_lease_state():
    table = Base.metadata.tables["portfolio_reservations"]
    assert {"request_id", "symbol", "direction", "risk_r", "volatility",
            "factor_exposure", "status", "lease_until"}.issubset(table.columns.keys())
    assert table.columns["request_id"].unique is True
    assert table.columns["lease_until"].nullable is False


def test_research_tables_keep_holdout_and_outcome_provenance():
    experiments = Base.metadata.tables["research_experiments"]
    results = Base.metadata.tables["experiment_book_results"]
    observations = Base.metadata.tables["experiment_observations"]
    assert {"code_sha", "config_hash", "data_snapshot", "train_start",
            "train_end", "oos_start", "oos_end", "holdout_locked"}.issubset(experiments.columns.keys())
    assert {"experiment_id", "signal_id", "fingerprint", "payload"}.issubset(observations.columns.keys())
    assert {"book", "outcome", "realized_r", "mfe_r", "mae_r", "hypothetical",
            "metadata_json"}.issubset(results.columns.keys())


def test_midas_specific_models_remain_registered():
    # Compatibility restoration must not displace Midas's existing schema.
    assert "signal_delivery_outbox" in Base.metadata.tables
    assert "configuration_registry" in Base.metadata.tables
    assert "configuration_evaluations" in Base.metadata.tables
    assert "config_sync_states" in Base.metadata.tables
    assert models.SignalDeliveryOutbox.__tablename__ == "signal_delivery_outbox"


def test_migration_is_additive_and_follows_current_head():
    migration = Path(__file__).parents[1] / "migrations" / "versions" / "0017_restore_durable_execution_research_schema.py"
    source = migration.read_text(encoding="utf-8")
    assert 'revision = "0017"' in source
    assert 'down_revision = "0016"' in source
    assert "def upgrade()" in source
    assert "def downgrade()" in source
    for table in (
        "research_experiments",
        "experiment_observations",
        "experiment_book_results",
        "validation_runs",
        "promotion_decision_audit",
        "execution_ledger",
        "portfolio_reservations",
    ):
        assert f'"{table}"' in source
