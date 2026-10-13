from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app import config_evaluation_model, config_registry_model, config_sync_state_model, models
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
        "execution_deal_events",
    }
    assert expected.issubset(Base.metadata.tables)


def test_execution_ledger_has_idempotency_and_reconciliation_fields():
    table = Base.metadata.tables["execution_ledger"]
    assert {"request_id", "portfolio_key", "signal_id", "state", "request_json", "result_json",
            "broker_order_id", "broker_deal_id", "broker_position_id",
            "checked_at", "sent_at", "reconciled_at", "lease_until",
            "latency_ms"}.issubset(table.columns.keys())
    request_id = table.columns["request_id"]
    assert request_id.unique is True
    assert request_id.nullable is False


def test_portfolio_reservations_preserve_risk_and_lease_state():
    table = Base.metadata.tables["portfolio_reservations"]
    assert {"request_id", "portfolio_key", "symbol", "direction", "risk_r", "volatility",
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
    assert config_registry_model.ConfigurationRegistry.__tablename__ == "configuration_registry"
    assert config_evaluation_model.ConfigurationEvaluation.__tablename__ == "configuration_evaluations"
    assert config_sync_state_model.ConfigSyncState.__tablename__ == "config_sync_states"
    assert models.SignalDeliveryOutbox.__tablename__ == "signal_delivery_outbox"


def test_migration_is_additive_and_follows_current_head():
    bridge_root = Path(__file__).parents[1]
    migration = bridge_root / "migrations" / "versions" / "0017_restore_durable_execution_research_schema.py"
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


def test_alembic_graph_has_one_head_at_0020():
    bridge_root = Path(__file__).parents[1]
    config = Config(str(bridge_root / "alembic.ini"))
    config.set_main_option("script_location", str(bridge_root / "migrations"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_current_head() == "0020"
    assert scripts.get_heads() == ["0020"]


def test_signal_outcomes_keep_signed_cashflows_separate_from_cost_magnitudes():
    table = Base.metadata.tables["signal_outcomes"]
    assert {"commission_cashflow", "swap_cashflow", "broker_fee_cashflow"}.issubset(
        table.columns.keys()
    )


def test_portfolio_scope_migration_follows_outcome_completeness_migration():
    bridge_root = Path(__file__).parents[1]
    migration = bridge_root / "migrations" / "versions" / "0019_scope_execution_portfolios.py"
    source = migration.read_text(encoding="utf-8")
    assert 'revision = "0019"' in source
    assert 'down_revision = "0018"' in source
    assert 'server_default=sa.text("' + "'legacy-unscoped'" + '")' in source
    assert '"portfolio_key"' in source


def test_execution_deal_events_are_deduplicated_by_account_and_broker_deal():
    table = Base.metadata.tables["execution_deal_events"]
    assert {
        "portfolio_key",
        "broker_deal_id",
        "broker_order_id",
        "broker_position_id",
        "entry_type",
        "deal_type",
        "volume",
        "price",
        "profit_cashflow",
        "commission_cashflow",
        "swap_cashflow",
        "fee_cashflow",
        "cashflows_known",
        "event_fingerprint",
        "payload_json",
    }.issubset(table.columns.keys())
    constraints = [
        constraint
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]
    assert any(
        set(constraint.columns.keys()) == {"portfolio_key", "broker_deal_id"}
        for constraint in constraints
    )


def test_deal_event_migration_follows_portfolio_scope():
    bridge_root = Path(__file__).parents[1]
    migration = bridge_root / "migrations" / "versions" / "0020_execution_deal_events.py"
    source = migration.read_text(encoding="utf-8")
    assert 'revision = "0020"' in source
    assert 'down_revision = "0019"' in source
    assert '"execution_deal_events"' in source
    assert "def upgrade()" in source
    assert "def downgrade()" in source
