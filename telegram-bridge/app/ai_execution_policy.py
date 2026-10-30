"""Fail-closed authorization policy for optional external-AI demo operations.

This module does not execute broker orders. It gates an auditable request for
an EA-owned action; the native EA still performs its own ledger reservation,
risk checks, order checks, and broker call.
"""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class AIExecutionDecision:
    allowed: bool
    reason: str


def authorize_demo_operation(
    *,
    enabled: bool,
    allowlisted_portfolios: Iterable[str],
    portfolio_key: str,
    actor: str,
    operation: str,
    operator_approval_ref: str,
    demo_validation_ref: str,
) -> AIExecutionDecision:
    """Authorize only explicit, evidence-backed, demo portfolio operations."""
    if not enabled:
        return AIExecutionDecision(False, "external AI execution authorization is disabled")
    if actor != "EXTERNAL_AI":
        return AIExecutionDecision(False, "unsupported actor")
    if operation not in {"OPEN", "MODIFY", "CLOSE"}:
        return AIExecutionDecision(False, "unsupported operation")
    if not portfolio_key or not portfolio_key.upper().startswith("DEMO:"):
        return AIExecutionDecision(False, "portfolio is not explicitly marked DEMO")
    if portfolio_key not in set(allowlisted_portfolios):
        return AIExecutionDecision(False, "portfolio is not in the server-side demo allowlist")
    if not operator_approval_ref.strip():
        return AIExecutionDecision(False, "operator approval evidence is required")
    if not demo_validation_ref.strip():
        return AIExecutionDecision(False, "demo validation evidence is required")
    return AIExecutionDecision(True, "demo-only authorization checks passed")
