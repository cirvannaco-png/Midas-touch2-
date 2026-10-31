from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAINTENANCE = ROOT / ".github" / "workflows" / "production-maintenance.yml"
HEALTH = ROOT / ".github" / "workflows" / "production-health-check.yml"


def test_subscription_maintenance_rejects_the_invalid_production_credential(client):
    response = client.post(
        "/admin/check-subscriptions",
        headers={"X-API-Key": "deliberately-invalid-key"},
    )
    assert response.status_code == 401


def test_ledger_health_rejects_the_invalid_production_credential(client):
    response = client.get(
        "/execution-ledger/health",
        headers={"X-API-Key": "deliberately-invalid-key"},
    )
    assert response.status_code == 401


def test_both_production_workflows_use_the_same_protected_bridge_key():
    maintenance = MAINTENANCE.read_text(encoding="utf-8")
    health = HEALTH.read_text(encoding="utf-8")
    assert "environment: production" in maintenance
    assert "environment: production" in health
    assert "BRIDGE_API_KEY: ${{ secrets.BRIDGE_API_KEY }}" in maintenance
    assert "BRIDGE_API_KEY: ${{ secrets.BRIDGE_API_KEY }}" in health
    assert "X-API-Key: ${BRIDGE_API_KEY}" in maintenance
    assert "X-API-Key: ${BRIDGE_API_KEY}" in health


def test_maintenance_fails_closed_after_public_health_preflight():
    workflow = MAINTENANCE.read_text(encoding="utf-8")
    assert "/health/db" in workflow
    assert "/admin/check-subscriptions" in workflow
    assert "case \"$http_code\"" in workflow
    assert "Subscription endpoint returned HTTP $http_code" in workflow


def test_health_workflow_does_not_retry_authentication_failures():
    workflow = HEALTH.read_text(encoding="utf-8")
    assert "/execution-ledger/health" in workflow
    assert "Authenticated execution-ledger health failed with HTTP" in workflow
    assert "^(000|502|503|504)$" in workflow



def test_every_execution_ledger_mutation_route_uses_single_bridge_authentication():
    source = (ROOT / "telegram-bridge/app/api/execution_ledger.py").read_text(encoding="utf-8")
    import re

    routes = list(re.finditer(r'@router\.post\("([^"]+)"\)', source))
    assert routes
    for route in routes:
        next_route = re.search(r"\n@router\.", source[route.end():])
        end = route.end() + next_route.start() if next_route else len(source)
        block = source[route.start():end]
        assert "Depends(verify_api_key)" in block, route.group(1)
    assert "verify_mt5_execution_key" not in source
