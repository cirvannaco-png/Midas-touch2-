from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "production-maintenance.yml"
HEALTH_WORKFLOW = ROOT / ".github" / "workflows" / "production-health-check.yml"
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
    assert workflow.count("for attempt in 1 2 3 4 5; do") >= 3
    assert workflow.count("retrying a read-only GET") >= 3



def test_each_production_mutation_is_behind_authenticated_ledger_preflight():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    guard = "Verify authenticated execution ledger before production mutation"
    assert workflow.count(guard) == 3
    assert workflow.count("secrets.BRIDGE_API_KEY") >= 3
    assert workflow.count("X-API-Key:") >= 3
    assert workflow.count("/execution-ledger/health") >= 3
    assert workflow.count("401") >= 3
    assert workflow.count("403") >= 3
    import re

    for job_name, mutation in (
        ("biweekly-recalibration", "Run and verify recalibration cycle"),
        ("daily-subscriptions", "Run and verify subscription sweep"),
        ("daily-delivery-recovery", "Recover failed or stale delivery notifications"),
    ):
        match = re.search(
            rf"(?ms)^  {job_name}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
            workflow,
        )
        assert match is not None, f"missing production job: {job_name}"
        job = match.group(1)
        assert guard in job
        assert job.index(guard) < job.index(mutation)
        assert "secrets.BRIDGE_API_KEY" in job
        assert "X-API-Key:" in job
    assert "credential values were not printed" in workflow


def test_production_health_workflow_rejects_bad_keys_without_exposing_secrets():
    workflow = HEALTH_WORKFLOW.read_text(encoding="utf-8")
    static_job = workflow.split("  service-database-health:", 1)[0]
    production_job = workflow.split("  service-database-health:", 1)[1]
    assert "secrets.BRIDGE_API_KEY" in production_job
    assert "X-API-Key:" in production_job
    assert "/execution-ledger/health" in production_job
    assert "${{ secrets.BRIDGE_API_KEY }}" not in static_job
    assert "401|403|422" in workflow
    assert "Payload values were not printed" in production_job


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
