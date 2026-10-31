from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
LEDGER = ROOT / "EA" / "includes" / "Execution" / "ExecutionLedgerClient.mqh"
BRIDGE = ROOT / "telegram-bridge" / "app" / "execution_control.py"


def test_broker_stop_changes_are_reconciled_after_position_manager_modifies_them():
    ea = EA.read_text(encoding="utf-8")
    manager_call = "g_positions.OnTick(atr);ReconcileManagedPositionStopModifications(atr);"
    assert manager_call in ea
    assert "SeedManagedPositionStopSnapshots(true);" in ea
    assert "SeedManagedPositionStopSnapshots(false);" in ea
    assert "POSITION_IDENTIFIER" in ea
    assert "POSITION_STOP_RECONCILIATION_FAILED" in ea
    assert "g_executionLedgerHealthy=false;" in ea


def test_position_modification_payload_records_before_and_after_stops():
    ea = EA.read_text(encoding="utf-8")
    ledger = LEDGER.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8")
    assert "previousStop,currentStop" in ea
    assert "previous_stop" in ledger and "current_stop" in ledger
    assert '"previous_stop"' in bridge and '"current_stop"' in bridge
    assert "position_modifications" in bridge
    assert "position modification sequence is out of order" in bridge


def test_unacknowledged_position_modification_blocks_future_entries():
    ea = EA.read_text(encoding="utf-8")
    start = ea.index("bool PrepareLedgerForSubmit(const TradeDecisionRecord &decision,const int legIndex,")
    body = ea[start:]
    assert 'InpRequireExecutionLedger && !g_executionLedgerHealthy' in body
    assert 'POSITION_STOP_RECONCILIATION_FAILED' in ea
    assert "new entries are blocked" in body
