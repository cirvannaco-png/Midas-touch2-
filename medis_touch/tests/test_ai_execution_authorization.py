from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from medis_touch.app.ai_execution_authorization import (
    AIExecutionApproval,
    authorize_ai_execution,
    sign_ai_execution_approval,
)
from medis_touch.app.execution_coordinator import GovernedExecutionCoordinator
from medis_touch.app.execution_governance import ExecutionConfig
from medis_touch.app.execution_models import ExecutionOrder, ExecutionPolicy, OrderStatus
from medis_touch.app.pretrade_risk import PreTradeLimits
from medis_touch.app.venue import SimulatedVenue


NOW = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)
AUTHORITY_SECRET = "ci-test-secret-that-is-at-least-thirty-two-bytes-long"


def _approval(**changes):
    base = AIExecutionApproval(
        approval_id="approval-001",
        approved_order_id="ai-order-001",
        idempotency_key="ai-idem-001",
        principal_id="account-owner-1",
        approved_by="account-owner-1",
        environment="DEMO",
        action="OPEN_ORDER",
        symbol="XAUUSD",
        side="BUY",
        max_quantity=0.05,
        max_notional=500.0,
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=2),
        explicit_user_consent=True,
    )
    signed = sign_ai_execution_approval(base, authority_secret=AUTHORITY_SECRET)
    unsigned = replace(base, **changes) if changes else base
    return sign_ai_execution_approval(unsigned, authority_secret=AUTHORITY_SECRET)


def _order(**changes):
    values = {
        "order_id": "ai-order-001",
        "decision_id": "ai-decision-001",
        "symbol": "XAUUSD",
        "side": "BUY",
        "quantity": 0.02,
        "policy": ExecutionPolicy.MARKET,
        "idempotency_key": "ai-idem-001",
        "metadata": {"origin": "AI", "approval_id": "approval-001", "principal_id": "account-owner-1"},
    }
    values.update(changes)
    return ExecutionOrder(**values)


def test_ai_execution_requires_exact_fresh_user_approved_demo_intent():
    authorize_ai_execution(
        _order(), _approval(), execution_environment="DEMO",
        reference_price=100.0, now=NOW, authority_secret=AUTHORITY_SECRET,
    )


@pytest.mark.parametrize(
    "approval,environment,order,price,match",
    [
        (_approval(explicit_user_consent=False), "DEMO", _order(), 100.0, "explicit user consent"),
        (_approval(expires_at=NOW), "DEMO", _order(), 100.0, "not currently valid"),
        (_approval(expires_at=NOW + timedelta(minutes=10)), "DEMO", _order(), 100.0, "cannot exceed five minutes"),
        (_approval(issued_at=NOW + timedelta(seconds=1)), "DEMO", _order(), 100.0, "not currently valid"),
        (_approval(action="CLOSE_ALL"), "DEMO", _order(), 100.0, "not allowlisted"),
        (_approval(environment="LIVE"), "DEMO", _order(), 100.0, "demo environment"),
        (_approval(symbol="EURUSD"), "DEMO", _order(), 100.0, "symbol and side"),
        (_approval(side="SELL"), "DEMO", _order(), 100.0, "symbol and side"),
        (_approval(max_quantity=0.01), "DEMO", _order(), 100.0, "quantity exceeds"),
        (_approval(max_notional=1.0), "DEMO", _order(), 100.0, "notional exceeds"),
        (_approval(), "LIVE", _order(), 100.0, "demo environment"),
        (_approval(), "DEMO", _order(idempotency_key=None), 100.0, "idempotency key"),
        (_approval(approved_order_id="other-order"), "DEMO", _order(), 100.0, "exact order and idempotency key"),
        (_approval(idempotency_key="other-idem"), "DEMO", _order(), 100.0, "exact order and idempotency key"),
        (_approval(), "DEMO", _order(metadata={"origin": "AI", "approval_id": "wrong", "principal_id": "account-owner-1"}), 100.0, "identity does not match"),
        (_approval(), "DEMO", _order(metadata={"origin": "AI", "approval_id": "approval-001", "principal_id": "different"}), 100.0, "principal does not match"),
        (_approval(), "DEMO", _order(metadata={"origin": "external", "approval_id": "approval-001", "principal_id": "account-owner-1"}), 100.0, "identity does not match"),
        (_approval(), "DEMO", _order(metadata={"origin": "AI", "bypass_ledger": True}), 100.0, "bypass governance"),
    ],
)
def test_ai_execution_denies_invalid_or_overreaching_approval(approval, environment, order, price, match):
    with pytest.raises(PermissionError, match=match):
        authorize_ai_execution(
            order, approval, execution_environment=environment,
            reference_price=price, now=NOW, authority_secret=AUTHORITY_SECRET,
        )


def test_coordinator_ai_entry_point_still_runs_risk_oms_and_reconciliation():
    config = ExecutionConfig("1", "MARKET", 10000, 5, 0.25, ("sim",), "model-v1")
    coordinator = GovernedExecutionCoordinator(
        SimulatedVenue("sim", 100.0, 100.2, 1000.0),
        config,
        approved_hash=config.config_hash,
        evidence_passed=True,
        execution_environment="DEMO",
        ai_approval_secret=AUTHORITY_SECRET,
    )
    outcome, _ = coordinator.execute_ai(
        _order(),
        approval=_approval(),
        reference_price=100.0,
        portfolio_notional=0.0,
        symbol_notional=0.0,
        daily_loss=0.0,
        spread_bps=2.0,
        limits=PreTradeLimits(1000, 10000, 5000, 100, 5),
        regime="normal",
        now=NOW,
    )
    assert outcome.status == OrderStatus.FILLED
    assert outcome.reconciled


def test_coordinator_ai_entry_point_refuses_live_environment():
    config = ExecutionConfig("1", "MARKET", 10000, 5, 0.25, ("sim",), "model-v1")
    coordinator = GovernedExecutionCoordinator(
        SimulatedVenue("sim", 100.0, 100.2, 1000.0),
        config,
        approved_hash=config.config_hash,
        evidence_passed=True,
    )
    with pytest.raises(PermissionError, match="demo environment"):
        coordinator.execute_ai(
            _order(),
            approval=_approval(),
            reference_price=100.0,
            portfolio_notional=0.0,
            symbol_notional=0.0,
            daily_loss=0.0,
            spread_bps=2.0,
            limits=PreTradeLimits(1000, 10000, 5000, 100, 5),
            regime="normal",
            now=NOW,
        )


def test_ai_execution_rejects_unsigned_or_tampered_approval():
    approval = _approval()
    with pytest.raises(PermissionError, match="signature is invalid"):
        authorize_ai_execution(
            _order(), replace(approval, signature="0" * 64),
            execution_environment="DEMO", reference_price=100.0,
            now=NOW, authority_secret=AUTHORITY_SECRET,
        )
    with pytest.raises(PermissionError, match="not configured"):
        authorize_ai_execution(
            _order(), approval, execution_environment="DEMO",
            reference_price=100.0, now=NOW, authority_secret=None,
        )


def test_ai_execution_approval_signer_rejects_short_authority_secret():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        sign_ai_execution_approval(_approval(), authority_secret="too-short")
