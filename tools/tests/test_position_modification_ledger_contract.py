from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_position_modification_is_intent_recorded_then_broker_confirmed():
    manager = (ROOT / "EA/includes/Execution/PositionManager.mqh").read_text(encoding="utf-8")
    client = (ROOT / "EA/includes/Execution/ExecutionLedgerClient.mqh").read_text(encoding="utf-8")
    api = (ROOT / "telegram-bridge/app/api/execution_ledger.py").read_text(encoding="utf-8")

    assert "PreparePositionModification" in manager
    assert "m_broker.ModifySLTP" in manager
    assert "ConfirmPositionModification" in manager
    assert "observedSL" not in manager
    assert "/execution-ledger/position-modification/prepare" in client
    assert "/execution-ledger/position-modification/confirm" in client
    assert "actual_stop_loss" in api


def test_failed_or_unresolved_modification_holds_admission_closed_until_snapshot():
    client = (ROOT / "EA/includes/Execution/ExecutionLedgerClient.mqh").read_text(encoding="utf-8")
    main = (ROOT / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    manager = (ROOT / "EA/includes/Execution/PositionManager.mqh").read_text(encoding="utf-8")

    assert "RequireReconciliation" in client
    assert "AdmissionReady()" in client
    assert "if(!g_executionLedger.AdmissionReady())" in main
    assert "m_ledger.RequireReconciliation()" in manager
    assert "g_executionLedger.MarkReconciled()" in main


def test_startup_snapshot_includes_observed_broker_stop_and_target():
    main = (ROOT / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    assert "requestIdOverride,sl,observedTP" in main
