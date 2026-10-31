"""Narrow GitHub Actions OIDC trust for production maintenance only.

This trust is intentionally separate from the EA/API-key credential. It grants
only a small set of operational HTTP routes to protected, main-branch workflows.
It never authorizes trading, order submission, stop changes, or research writes.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

OIDC_ISSUER = "https://token.actions.githubusercontent.com"
OIDC_AUDIENCE = "midas-touch2-production"
OIDC_JWKS_URL = f"{OIDC_ISSUER}/.well-known/jwks"
REPOSITORY = "cirvannaco-png/Midas-touch2-"
PRODUCTION_SUBJECT = f"repo:{REPOSITORY}:environment:production"
ALLOWED_EVENTS = frozenset({"schedule", "workflow_dispatch", "push"})
WORKFLOW_PATHS = {
    ".github/workflows/production-maintenance.yml",
    ".github/workflows/production-health-check.yml",
}
ROUTE_ALLOWLIST = {
    ("GET", "/execution-ledger/health"): WORKFLOW_PATHS,
    ("POST", "/admin/check-subscriptions"): frozenset({".github/workflows/production-maintenance.yml"}),
    ("POST", "/admin/run-cycle"): frozenset({".github/workflows/production-maintenance.yml"}),
    ("POST", "/retry-failed"): frozenset({".github/workflows/production-maintenance.yml"}),
    ("POST", "/trade/retry-failed"): frozenset({".github/workflows/production-maintenance.yml"}),
}


class ProductionOIDCError(ValueError):
    """Raised when a GitHub Actions identity is not trusted for this route."""


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(OIDC_JWKS_URL, cache_keys=True, lifespan=300)


def _verified_claims(token: str) -> dict[str, Any]:
    if not token or len(token) > 16384:
        raise ProductionOIDCError("invalid production workflow token")
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=OIDC_AUDIENCE,
            issuer=OIDC_ISSUER,
            leeway=30,
            options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub"]},
        )
    except Exception as exc:
        # Do not expose token, signature, or verifier details to callers/logs.
        raise ProductionOIDCError("production workflow token verification failed") from exc
    if not isinstance(claims, dict):
        raise ProductionOIDCError("invalid production workflow claims")
    return claims


def authorize_production_workflow_claims(
    claims: dict[str, Any], *, method: str, path: str
) -> bool:
    """Authorize an already signature-verified identity for one exact route."""
    workflows = ROUTE_ALLOWLIST.get((method.upper(), path))
    if workflows is None:
        return False
    if claims.get("iss") != OIDC_ISSUER or claims.get("aud") != OIDC_AUDIENCE:
        return False
    if claims.get("repository") != REPOSITORY:
        return False
    if claims.get("ref") != "refs/heads/main":
        return False
    if claims.get("environment") != "production":
        return False
    if claims.get("sub") != PRODUCTION_SUBJECT:
        return False
    if claims.get("event_name") not in ALLOWED_EVENTS:
        return False
    workflow_ref = claims.get("workflow_ref")
    if not isinstance(workflow_ref, str):
        return False
    prefix = f"{REPOSITORY}/"
    if not workflow_ref.startswith(prefix) or "@" not in workflow_ref:
        return False
    workflow_path, ref = workflow_ref[len(prefix):].rsplit("@", 1)
    return workflow_path in workflows and workflow_path in WORKFLOW_PATHS and ref == "refs/heads/main"


def verify_production_workflow_token(token: str, *, method: str, path: str) -> bool:
    """Verify the JWT signature and the endpoint-specific workflow policy."""
    return authorize_production_workflow_claims(
        _verified_claims(token), method=method, path=path
    )
