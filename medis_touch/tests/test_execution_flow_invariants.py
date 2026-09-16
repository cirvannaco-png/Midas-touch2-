from medis_touch.app.child_execution import ChildOrderExecutor
from medis_touch.app.execution_models import ExecutionOrder, ExecutionPolicy, OrderStatus, VenueQuote
from medis_touch.app.execution_router import SmartOrderRouter
from medis_touch.app.oms import OrderManager
from medis_touch.app.pretrade_risk import PreTradeLimits, evaluate
from medis_touch.app.reconciliation import reconcile
from medis_touch.app.tca import calculate_tca


def test_pretrade_oms_router_child_tca_reconciliation_flow() -> None:
    order = ExecutionOrder(
        order_id="flow-1", decision_id="decision-1", symbol="XAUUSD", side="BUY", quantity=4.0,
        policy=ExecutionPolicy.TWAP, idempotency_key="flow-idem-1", metadata={"slices": 2},
    )
    risk = evaluate(
        order, reference_price=100.0, portfolio_notional=0.0, symbol_notional=0.0, daily_loss=0.0,
        spread_bps=2.0, limits=PreTradeLimits(1000.0, 5000.0, 2000.0, 100.0, 5.0),
    )
    assert risk.allowed
    oms = OrderManager()
    stored = oms.submit(order)
    oms.transition(order.order_id, OrderStatus.VALIDATED)
    oms.transition(order.order_id, OrderStatus.ROUTING)
    quote = VenueQuote("v1", "XAUUSD", 99.9, 100.1, 100.0, 5.0)
    route = SmartOrderRouter().route([quote], order.quantity, urgency=0.5)
    assert route.venue == "v1"
    children = ChildOrderExecutor().build_children(stored)
    assert len(children) == 2
    assert sum(child.quantity for child in children) == order.quantity
    oms.transition(order.order_id, OrderStatus.WORKING)
    result = reconcile(oms.get(order.order_id), OrderStatus.WORKING)
    assert result.matched and result.action == "RESUME"
    tca = calculate_tca(
        order_id=order.order_id, side=order.side, quantity=order.quantity, decision_price=100.0,
        arrival_price=100.0, average_fill_price=100.05, spread=0.2, estimated_market_impact=0.01,
    )
    assert tca.implementation_shortfall > 0
    assert tca.slippage_cost > 0


def test_unknown_broker_state_never_resumes_exposure() -> None:
    order = ExecutionOrder("flow-2", "decision-2", "XAUUSD", "BUY", 1.0)
    result = reconcile(order, OrderStatus.UNKNOWN)
    assert not result.matched
    assert result.action == "FREEZE_AND_QUERY"
