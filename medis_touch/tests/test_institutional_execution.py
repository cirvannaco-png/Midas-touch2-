from medis_touch.app.execution_models import ExecutionOrder, ExecutionPolicy, OrderStatus, VenueQuote
from medis_touch.app.execution_router import SmartOrderRouter
from medis_touch.app.execution_surveillance import inspect
from medis_touch.app.oms import OrderManager
from medis_touch.app.reconciliation import reconcile
from medis_touch.app.tca import calculate_tca


def test_oms_is_idempotent_and_rejects_invalid_transition():
    oms = OrderManager()
    order = ExecutionOrder("o1", "d1", "XAUUSD", "BUY", 1.0, idempotency_key="d1:XAUUSD")
    assert oms.submit(order).order_id == "o1"
    assert oms.submit(ExecutionOrder("o2", "d1", "XAUUSD", "BUY", 1.0, idempotency_key="d1:XAUUSD")).order_id == "o1"
    oms.transition("o1", OrderStatus.VALIDATED)
    oms.transition("o1", OrderStatus.ROUTING)
    try:
        oms.transition("o1", OrderStatus.FILLED)
        assert False, "invalid transition accepted"
    except ValueError:
        pass


def test_router_prefers_healthy_liquid_venue():
    router = SmartOrderRouter()
    quotes = [
        VenueQuote("slow", "XAUUSD", 100, 101, 10, 500, 0.8, 0.1, 4),
        VenueQuote("good", "XAUUSD", 100, 100.5, 20, 20, 0.99, 0.01, 1),
    ]
    assert router.route(quotes, 5).venue == "good"


def test_tca_calculates_signed_shortfall():
    result = calculate_tca(order_id="o1", side="BUY", quantity=2, decision_price=100, arrival_price=100.1, average_fill_price=100.2)
    assert result.implementation_shortfall == 0.4
    assert result.slippage_cost == 0.2


def test_reconciliation_fails_closed_when_broker_is_unknown():
    order = ExecutionOrder("o1", "d1", "XAUUSD", "BUY", 1, status=OrderStatus.WORKING)
    result = reconcile(order, OrderStatus.UNKNOWN)
    assert not result.matched
    assert result.action == "FREEZE_AND_QUERY"


def test_surveillance_detects_duplicate_and_venue_failure():
    alerts = inspect(rejection_rate=0.0, slippage_bps=0.0, p99_latency_ms=10, duplicate_order_count=1, venue_healthy=False)
    assert {a.code for a in alerts} == {"DUPLICATE_ORDER", "VENUE_UNHEALTHY"}
