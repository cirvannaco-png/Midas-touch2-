from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "production-maintenance.yml"
ROUTES = ROOT / "telegram-bridge" / "app" / "routes.py"
RECOVERY = ROOT / "medis_touch" / "app" / "execution_recovery.py"
RECONCILIATION = ROOT / "medis_touch" / "app" / "reconciliation.py"
COORDINATOR = ROOT / "medis_touch" / "app" / "execution_coordinator.py"


def test_production_maintenance_has_health_preflight_and_strict_cycle_identity():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count("/health/db") >= 3
    assert 'result.get("database") != "connected"' in workflow
    assert "not cycle_id.strip()" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "--retry 0" in workflow


def test_delivery_recovery_schedule_and_contract_are_wired():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    routes = ROUTES.read_text(encoding="utf-8")
    assert 'cron: "0 8 * * *"' in workflow
    assert "daily-delivery-recovery" in workflow
    assert '"/retry-failed"' in workflow
    assert '"/trade/retry-failed"' in workflow
    assert 'select(func.count()).select_from(TradeEvent)' in routes
    assert 'select(func.count()).select_from(Signal)' in routes
    assert routes.count('"remaining_failed": int(remaining or 0)') == 2
    assert '"processed": len(failed_events)' in routes
    assert '"processed": len(failed_signals)' in routes


def test_durable_fill_events_are_idempotent_and_quantity_bounded():
    recovery = RECOVERY.read_text(encoding="utf-8")
    coordinator = COORDINATOR.read_text(encoding="utf-8")
    assert "execution_recovery_fills" in recovery
    assert "requested_quantity REAL" in recovery
    assert "fill_id=fill.fill_id" in coordinator
    assert "cumulative fill quantity exceeds requested_quantity" in recovery
    assert "fill_id was reused with different quantity or price" in recovery


def test_reconciliation_fails_closed_without_quantitative_broker_evidence():
    reconciliation = RECONCILIATION.read_text(encoding="utf-8")
    assert "if observed_filled is None:" in reconciliation
    assert 'return unresolved("FREEZE_AND_QUERY", "broker fill quantity unavailable")' in reconciliation
    assert "OrderStatus.RECOVERY_REQUIRED" in reconciliation


def test_empty_ea_backend_history_is_not_mistaken_for_parity():
    recovery = RECOVERY.read_text(encoding="utf-8")
    assert "return bool(ea and backend and ea == backend)" in recovery
    assert "state event sequence must increase monotonically" in recovery
    assert "decision identity/fingerprint cannot change within an order" in recovery
