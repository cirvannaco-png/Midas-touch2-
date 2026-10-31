"""Explicit user-consent contract for AI-originated execution.

This module is a pre-execution authorization layer. It does not grant the
strategy a bypass around normal risk, venue, admission, ledger, or broker checks.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from .execution_models import ExecutionOrder


@dataclass(frozen=True)
class AIExecutionApproval:
    approval_id: str
    principal_id: str
    approved_by: str
    environment: str
    action: str
    symbol: str
    side: str
    max_quantity: float
    max_notional: float
    issued_at: datetime
    expires_at: datetime
    explicit_user_consent: bool


def authorize_ai_execution(
    order: ExecutionOrder,
    approval: AIExecutionApproval,
    *,
    execution_environment: str,
    reference_price: float,
    now: datetime,
) -> None:
    """Raise PermissionError unless this exact order is approved for demo only."""
    required = (approval.approval_id, approval.principal_id, approval.approved_by, order.idempotency_key)
    if any(not isinstance(value, str) or not value.strip() for value in required):
        raise PermissionError("AI execution requires a principal, approval, and idempotency key")
    if approval.approved_by != approval.principal_id:
        raise PermissionError("AI execution approval is not bound to the requesting principal")
    if approval.explicit_user_consent is not True:
        raise PermissionError("explicit user consent is required for AI execution")
    if approval.action != "OPEN_ORDER":
        raise PermissionError("AI execution action is not allowlisted")
    if execution_environment.strip().upper() != "DEMO" or approval.environment.strip().upper() != "DEMO":
        raise PermissionError("AI-originated execution is restricted to an explicitly configured demo environment")
    if approval.issued_at.tzinfo is None or approval.issued_at.utcoffset() is None:
        raise PermissionError("AI approval issue time must be timezone-aware")
    if approval.expires_at.tzinfo is None or approval.expires_at.utcoffset() is None:
        raise PermissionError("AI approval expiry must be timezone-aware")
    if now.tzinfo is None or now.utcoffset() is None:
        raise PermissionError("AI authorization time must be timezone-aware")
    issued = approval.issued_at.timestamp()
    expires = approval.expires_at.timestamp()
    current = now.timestamp()
    if issued > current or expires <= current or expires <= issued:
        raise PermissionError("AI execution approval is not currently valid")
    if not all(math.isfinite(value) for value in (order.quantity, reference_price, approval.max_quantity, approval.max_notional)):
        raise PermissionError("AI order and approval limits must be finite")
    if order.quantity <= 0 or reference_price <= 0 or approval.max_quantity <= 0 or approval.max_notional <= 0:
        raise PermissionError("AI order and approval limits must be positive")
    if order.symbol != approval.symbol or order.side.upper() != approval.side.upper():
        raise PermissionError("AI order does not match the approved symbol and side")
    if order.quantity > approval.max_quantity:
        raise PermissionError("AI order quantity exceeds the user-approved limit")
    if order.quantity * reference_price > approval.max_notional:
        raise PermissionError("AI order notional exceeds the user-approved limit")
    bypass_fields = {
        "portfolio_admitted",
        "risk_gate_passed",
        "ledger_ready",
        "execution_approved",
        "skip_risk",
        "bypass_ledger",
        "admin_override",
    }
    if bypass_fields.intersection(order.metadata):
        raise PermissionError("AI order metadata cannot assert or bypass governance decisions")
