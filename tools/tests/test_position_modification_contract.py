from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POSITION_MANAGER = ROOT / "EA" / "includes" / "Execution" / "PositionManager.mqh"
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
LEDGER_CLIENT = ROOT / "EA" / "includes" / "Execution" / "ExecutionLedgerClient.mqh"
API = ROOT / "telegram-bridge" / "app" / "api" / "execution_ledger.py"
MODEL = ROOT / "telegram-bridge" / "app" / "models.py"
MIGRATION = ROOT / "telegram-bridge" / "migrations" / "versions" / "0021_execution_position_modifications.py"


def test_stop_modification_queue_is_durable_and_fail_closed():
    manager = POSITION_MANAGER.read_text(encoding="utf-8")
    ea = EA.read_text(encoding="utf-8")
    client = LEDGER_CLIENT.read_text(encoding="utf-8")
    assert "FILE_COMMON" in manager
    assert "chartSymbol=_Symbol" in manager
    assert "LoadPendingModifications();" in manager
    assert "SavePendingModifications()" in manager
    assert "m_pendingPersistenceHealthy=SavePendingModifications();" in manager
    assert "FileMove(temporary,FILE_COMMON" in manager
    assert "RetryPendingLedgerReconciliation" in manager
    assert "HasPendingModification(currentPositionIdentifier)" in manager
    assert "POSITION_MODIFICATION_LEDGER_PENDING" in ea
    assert "g_executionLedgerHealthy=false" in ea
    assert '"/execution-ledger/position-modification"' in client


def test_position_modification_event_is_authenticated_immutable_and_idempotent():
    api = API.read_text(encoding="utf-8")
    model = MODEL.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/execution-ledger"' in api
    assert '@router.post("/position-modification")' in api
    assert "_auth: bool = Depends(verify_api_key)" in api
    assert "event_fingerprint" in api
    assert "evidence_ref was reused with different broker state" in api
    assert "ExecutionPositionModification" in model
    assert "uq_execution_position_mod_portfolio_evidence" in model
    assert 'revision = "0021"' in migration
    assert 'down_revision = "0020"' in migration
