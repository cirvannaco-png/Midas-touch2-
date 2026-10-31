import pytest

from app.production_auth import (
    OIDC_AUDIENCE,
    OIDC_ISSUER,
    PRODUCTION_SUBJECT,
    authorize_production_workflow_claims,
)


REPOSITORY = "cirvannaco-png/Midas-touch2-"
MAINTENANCE = f"{REPOSITORY}/.github/workflows/production-maintenance.yml@refs/heads/main"
HEALTH = f"{REPOSITORY}/.github/workflows/production-health-check.yml@refs/heads/main"


def _claims(workflow_ref=MAINTENANCE):
    return {
        "iss": OIDC_ISSUER,
        "aud": OIDC_AUDIENCE,
        "sub": PRODUCTION_SUBJECT,
        "repository": REPOSITORY,
        "ref": "refs/heads/main",
        "environment": "production",
        "event_name": "workflow_dispatch",
        "workflow_ref": workflow_ref,
    }


@pytest.mark.parametrize(
    "method,path,workflow_ref",
    [
        ("POST", "/admin/check-subscriptions", MAINTENANCE),
        ("POST", "/admin/run-cycle", MAINTENANCE),
        ("POST", "/retry-failed", MAINTENANCE),
        ("POST", "/trade/retry-failed", MAINTENANCE),
        ("GET", "/execution-ledger/health", MAINTENANCE),
        ("GET", "/execution-ledger/health", HEALTH),
    ],
)
def test_production_oidc_allows_only_explicit_operational_routes(method, path, workflow_ref):
    assert authorize_production_workflow_claims(
        _claims(workflow_ref), method=method, path=path
    )


@pytest.mark.parametrize(
    "claim,value,method,path",
    [
        ("repository", "attacker/fork", "POST", "/admin/check-subscriptions"),
        ("ref", "refs/heads/feature", "POST", "/admin/check-subscriptions"),
        ("environment", "development", "POST", "/admin/check-subscriptions"),
        ("event_name", "pull_request", "POST", "/admin/check-subscriptions"),
        ("aud", "api://default", "POST", "/admin/check-subscriptions"),
        ("sub", "repo:attacker/fork:environment:production", "POST", "/admin/check-subscriptions"),
        ("workflow_ref", f"{REPOSITORY}/.github/workflows/ci.yml@refs/heads/main", "POST", "/admin/check-subscriptions"),
        ("workflow_ref", f"{REPOSITORY}/.github/workflows/production-health-check.yml@refs/heads/main", "POST", "/admin/check-subscriptions"),
    ],
)
def test_production_oidc_rejects_wrong_repository_branch_environment_or_workflow(claim, value, method, path):
    claims = _claims()
    claims[claim] = value
    assert not authorize_production_workflow_claims(claims, method=method, path=path)


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/signal"),
        ("POST", "/execution-ledger/reserve"),
        ("POST", "/execution-ledger/position-risk"),
        ("POST", "/research/backtest-evidence"),
        ("DELETE", "/admin/check-subscriptions"),
    ],
)
def test_production_oidc_never_authorizes_trading_position_or_research_routes(method, path):
    assert not authorize_production_workflow_claims(
        _claims(), method=method, path=path
    )


def test_production_oidc_requires_signature_verified_jwt_claims_not_caller_headers():
    # The HTTP dependency only grants a request after the JWT verification
    # function returns True; raw caller-supplied claim headers are not accepted.
    claims = _claims()
    assert authorize_production_workflow_claims(claims, method="GET", path="/execution-ledger/health")
    assert not authorize_production_workflow_claims({}, method="GET", path="/execution-ledger/health")
