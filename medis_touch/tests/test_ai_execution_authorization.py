from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from medis_touch.app.ai_execution_authorization import AIExecutionApproval, authorize_ai_execution
from medis_touch.app.execution_coordinator import GovernedExecutionCoordinator
from medis_touch.app.execution_governance import ExecutionConfig
from medis_touch.app.execution_models import ExecutionOrder, ExecutionPolicy, OrderStatus
from medis_touch.app.pretrade_risk import PreTradeLimits
from medis_touch.app.venue import SimulatedVenue


NOW = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)


def _approval(**changes):
    base = AIExecutionApproval(
        approval_id="approval-001",
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
    return replace(base, **changes)


def _order(**changes):
    values = {
        "order_id": "ai-order-001",
        "decision_id": "ai-decision-001",
        "symbol": "XAUUSD",
        "side": "BUY",
        "quantity": 0.02,
        "policy": ExecutionPolicy.MARKET,
        "idempotency_key": "ai-idem-001",
        "metadata": {"origin": "AI", "approval_id": "approval-001"},
    }
    values.update(changes)
    return ExecutionOrder(**values)


def test_ai_execution_requires_exact_fresh_user_approved_demo_intent():
    authorize_ai_execution(
        _order(), _approval(), execution_environment="DEMO",
        reference_price=100.0, now=NOW,
    )


@pytest.mark.parametrize(
    "approval,environment,order,price,match",
    [
        (_approval(explicit_user_consent=False), "DEMO", _order(), 100.0, "explicit user consent"),
        (_approval(expires_at=NOW), "DEMO", _order(), 100.0, "not currently valid"),
        (_approval(issued_at=NOW + timedelta(seconds=1)), "DEMO", _order(), 100.0, "not currently valid"),
        (_approval(action="CLOSE_ALL"), "DEMO", _order(), 100.0, "not allowlisted"),
        (_approval(environment="LIVE"), "DEMO", _order(), 100.0, "demo environment"),
        (_approval(symbol="EURUSD"), "DEMO", _order(), 100.0, "symbol and side"),
        (_approval(side="SELL"), "DEMO", _order(), 100.0, "symbol and side"),
        (_approval(max_quantity=0.01), "DEMO", _order(), 100.0, "quantity exceeds"),
        (_approval(max_notional=1.0), "DEMO", _order(), 100.0, "notional exceeds"),
        (_approval(), "LIVE", _order(), 100.0, "demo environment"),
        (_approval(), "DEMO", _order(idempotency_key=None), 100.0, "idempotency key"),
        (_approval(), "DEMO", _order(metadata={"origin": "AI", "bypass_ledger": True}), 100.0, "bypass governance"),
    ],
)
def test_ai_execution_denies_invalid_or_overreaching_approval(approval, environment, order, price, match):
    with pytest.raises(PermissionError, match=match):
        authorize_ai_execution(
            order, approval, execution_environment=environment,
            reference_price=price, now=NOW,
        )


def test_coordinator_ai_entry_point_still_runs_risk_oms_and_reconciliation():
    config = ExecutionConfig("1", "MARKET", 10000, 5, 0.25, ("sim",), "model-v1")
    coordinator = GovernedExecutionCoordinator(
        SimulatedVenue("sim", 100.0, 100.2, 1000.0),
        config,
        approved_hash=config.config_hash,
        evidence_passed=True,
        execution_environment="DEMO",
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
