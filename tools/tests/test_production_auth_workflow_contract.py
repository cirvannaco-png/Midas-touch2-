from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAINTENANCE = ROOT / ".github" / "workflows" / "production-maintenance.yml"
HEALTH = ROOT / ".github" / "workflows" / "production-health-check.yml"
BRIDGE_CONFIG = ROOT / "telegram-bridge" / "app" / "config.py"
BRIDGE_ROUTES = ROOT / "telegram-bridge" / "app" / "routes.py"
RENDER_BLUEPRINT = ROOT / "render.yaml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_production_maintenance_subscription_failure_is_authenticated_and_fail_closed():
    workflow = _read(MAINTENANCE)
    assert 'BRIDGE_API_KEY: ${{ secrets.BRIDGE_API_KEY }}' in workflow
    assert '--header "X-API-Key: ${BRIDGE_API_KEY}"' in workflow
    assert '"/admin/check-subscriptions"' in workflow
    assert 'case "$http_code" in' in workflow
    assert '*) echo "::error::Subscription endpoint returned HTTP $http_code."' in workflow
    assert "no automatic retry was attempted" in workflow
    assert 'environment: production' in workflow
    assert "permissions:\n  contents: read" in workflow


def test_production_health_check_uses_same_credential_for_authenticated_ledger_probe():
    workflow = _read(HEALTH)
    assert 'BRIDGE_API_KEY: ${{ secrets.BRIDGE_API_KEY }}' in workflow
    assert '--header "X-API-Key: ${BRIDGE_API_KEY}"' in workflow
    assert "/execution-ledger/health" in workflow
    assert 'environment: production' in workflow
    assert 'secrets.BRIDGE_API_KEY' in workflow
    assert "401|403|422" in workflow


def test_bridge_and_render_share_a_single_explicit_authentication_contract():
    config = _read(BRIDGE_CONFIG)
    routes = _read(BRIDGE_ROUTES)
    blueprint = _read(RENDER_BLUEPRINT)
    assert "BRIDGE_API_KEY: str = \"\"" in config
    assert "def bridge_api_key(self)" in config
    assert "expected_key = settings.bridge_api_key" in routes
    assert "if not expected_key or not secrets.compare_digest" in routes
    assert "- key: BRIDGE_API_KEY\n        sync: false" in blueprint
    assert "- key: SECRET_KEY\n        sync: false" in blueprint
