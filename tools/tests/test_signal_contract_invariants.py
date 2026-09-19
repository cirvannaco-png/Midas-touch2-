from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_ea_publishes_complete_setup_provenance():
    publisher = _read("EA/includes/Signals/SignalPublisher.mqh")
    assert '\\"invalidation\\":' in publisher
    assert '\\"final_tp\\":' in publisher
    assert '\\"strategy\\":' in publisher
    assert "EnumToString(r.selected_strategy)" in publisher


def test_ea_terminal_csv_audit_contract_is_explicit():
    publisher = _read("EA/includes/Signals/SignalPublisher.mqh")
    assert '"DecisionID","Time","Symbol","Direction","Entry","SL","TP1","TP2","FinalTP","Confidence","Action"' in publisher
    assert 'FileWrite(m_fileHandle,dec.decision_id,TimeToString(dec.decided_time,TIME_DATE|TIME_MINUTES),dec.symbol,dir,entry,dec.setup.stop_loss,dec.setup.tp1,dec.setup.tp2,dec.setup.final_tp,dec.setup.confidence,EnumToString(dec.action)' in publisher
    # The network payload is canonical; the CSV remains an intentionally
    # compact terminal-delivery audit rather than a second source of truth.
    assert '\\"invalidation\\":%.8f' in publisher
    assert '\\"strategy\\":\\"%s\\"' in publisher


def test_bridge_accepts_and_persists_complete_setup_provenance():
    routes = _read("telegram-bridge/app/routes.py")
    assert "invalidation: float | None" in routes
    assert "final_tp: float | None" in routes
    assert "strategy: str | None" in routes
    assert "invalidation=payload.invalidation" in routes
    assert "final_tp=payload.final_tp" in routes
    assert "strategy=payload.strategy" in routes


def test_copy_feed_preserves_setup_provenance():
    routes = _read("telegram-bridge/app/routes.py")
    assert "invalidation: float | None = None" in routes
    assert "final_tp: float | None = None" in routes
    assert "strategy: str | None = None" in routes
    assert "invalidation=s.invalidation" in routes
    assert "final_tp=s.final_tp" in routes
    assert "strategy=s.strategy" in routes


def test_bridge_validation_preserves_thesis_vs_protective_stop_boundary():
    validator = _read("telegram-bridge/app/validator.py")
    assert "thesis invalidation must be below entry price" in validator
    assert "protective stop must be below thesis invalidation" in validator
    assert "final TP must be above TP2" in validator
    assert "thesis invalidation must be above entry price" in validator
    assert "protective stop must be above thesis invalidation" in validator
    assert "final TP must be below TP2" in validator


def test_decision_persistence_database_schema_and_migration_match():
    store = _read("EA/includes/Decision/DecisionStore.mqh")
    model = _read("telegram-bridge/app/models.py")
    migration = _read("telegram-bridge/migrations/versions/0012_canonical_trade_setup_contract.py")
    assert "rec.setup.invalidation" in store
    assert "rec.setup.reasons.selected_strategy" in store
    assert "invalidation = Column(Float, nullable=True)" in model
    assert "final_tp = Column(Float, nullable=True)" in model
    assert "strategy = Column(String(64), nullable=True, index=True)" in model
    assert 'sa.Column("invalidation", sa.Float(), nullable=True)' in migration
    assert 'sa.Column("final_tp", sa.Float(), nullable=True)' in migration
    assert 'sa.Column("strategy", sa.String(64), nullable=True)' in migration
    assert 'op.create_index("ix_signals_strategy", "signals", ["strategy"])' in migration


def test_outcome_provenance_contract_is_complete():
    publisher = _read("EA/includes/Signals/SignalPublisher.mqh")
    tracker = _read("EA/includes/Trading/OutcomeTracker.mqh")
    routes = _read("telegram-bridge/app/routes.py")
    model = _read("telegram-bridge/app/models.py")
    assert "resolution" in publisher and "commission_cost" in publisher and "strategy" in publisher
    assert "PublishIfConfigured(m_pending[idx], coarseOutcome, outcome, ambiguous)" in tracker
    assert "EnumToString(r.selected_strategy)" in tracker
    assert "strategy: str | None" in routes and "resolution: str | None" in routes
    assert "commission_cost: float | None" in routes and "slippage_cost: float | None" in routes
    assert "strategy = Column(String(64), nullable=True, index=True)" in model
    assert "resolution = Column(String(64), nullable=True, index=True)" in model


def test_temporal_outcome_contract_uses_signal_timestamp():
    model = _read("telegram-bridge/app/models.py")
    routes = _read("telegram-bridge/app/routes.py")
    migration = _read("telegram-bridge/migrations/versions/0014_outcome_provenance_and_execution_costs.py")
    walk = _read("tools/walk_forward.py")
    assert "signal_time = Column(DateTime(timezone=True), nullable=True, index=True)" in model
    assert "row.signal_time = source_signal.signal_time or source_signal.received_at" in routes
    assert 'sa.Column("signal_time", sa.DateTime(timezone=True), nullable=True)' in migration
    assert 'getattr(row, "signal_time", None) or getattr(row, "received_at", None)' in walk
    assert "time_basis" in walk
