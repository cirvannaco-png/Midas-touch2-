"""Explicit user-consent contract for AI-originated execution.

This module is a pre-execution authorization layer. It does not grant the
strategy a bypass around normal risk, venue, admission, ledger, or broker checks.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass, replace
from datetime import datetime

from .execution_models import ExecutionOrder


@dataclass(frozen=True)
class AIExecutionApproval:
    approval_id: str
    approved_order_id: str
    idempotency_key: str
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
    signature: str = ""


def _approval_payload(approval: AIExecutionApproval) -> bytes:
    """Stable representation bound to identity, order, limits, environment and expiry."""
    payload = {
        "approval_id": approval.approval_id,
        "approved_order_id": approval.approved_order_id,
        "idempotency_key": approval.idempotency_key,
        "principal_id": approval.principal_id,
        "approved_by": approval.approved_by,
        "environment": approval.environment,
        "action": approval.action,
        "symbol": approval.symbol,
        "side": approval.side,
        "max_quantity": approval.max_quantity,
        "max_notional": approval.max_notional,
        "issued_at": approval.issued_at.isoformat(),
        "expires_at": approval.expires_at.isoformat(),
        "explicit_user_consent": approval.explicit_user_consent,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sign_ai_execution_approval(
    approval: AIExecutionApproval, *, authority_secret: str | bytes
) -> AIExecutionApproval:
    """Issue the HMAC signature at the trusted consent-authority boundary."""
    secret = authority_secret.encode("utf-8") if isinstance(authority_secret, str) else authority_secret
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("AI execution approval authority secret must contain at least 32 bytes")
    signature = hmac.new(secret, _approval_payload(approval), hashlib.sha256).hexdigest()
    return replace(approval, signature=signature)


def authorize_ai_execution(
    order: ExecutionOrder,
    approval: AIExecutionApproval,
    *,
    execution_environment: str,
    reference_price: float,
    now: datetime,
    authority_secret: str | bytes | None,
) -> None:
    """Raise PermissionError unless this exact order is approved for demo only."""
    required = (
        approval.approval_id,
        approval.approved_order_id,
        approval.idempotency_key,
        approval.principal_id,
        approval.approved_by,
        order.idempotency_key,
    )
    if any(not isinstance(value, str) or not value.strip() for value in required):
        raise PermissionError("AI execution requires a principal, approval, and idempotency key")
    secret = authority_secret.encode("utf-8") if isinstance(authority_secret, str) else authority_secret
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise PermissionError("trusted AI approval authority is not configured")
    expected_signature = hmac.new(secret, _approval_payload(approval), hashlib.sha256).hexdigest()
    if not approval.signature or not hmac.compare_digest(approval.signature, expected_signature):
        raise PermissionError("AI execution approval signature is invalid or untrusted")
    if approval.approved_by != approval.principal_id:
        raise PermissionError("AI execution approval is not bound to the requesting principal")
    if approval.approved_order_id != order.order_id or approval.idempotency_key != order.idempotency_key:
        raise PermissionError("AI execution approval is not bound to this exact order and idempotency key")
    if order.metadata.get("origin") != "AI" or order.metadata.get("approval_id") != approval.approval_id:
        raise PermissionError("AI execution approval identity does not match the order metadata")
    if order.metadata.get("principal_id") != approval.principal_id:
        raise PermissionError("AI execution approval principal does not match the order metadata")
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
    if expires - issued > 300:
        raise PermissionError("AI execution approval validity window cannot exceed five minutes")
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
