# ruff: noqa: I001

from math import inf, nan

import pytest

from medis_touch.app.execution_models import ExecutionFill, ExecutionOrder, OrderStatus, VenueQuote
from medis_touch.app.execution_policy import adaptive_policy, pov_schedule, twap_schedule, vwap_schedule
from medis_touch.app.execution_router import SmartOrderRouter
from medis_touch.app.execution_surveillance import inspect
from medis_touch.app.oms import OrderManager
from medis_touch.app.pretrade_risk import PreTradeLimits, evaluate
from medis_touch.app.reconciliation import reconcile
from medis_touch.app.tca import calculate_tca
from medis_touch.app.venue import SimulatedVenue


def test_oms_is_idempotent_and_rejects_invalid_transition():
    oms = OrderManager()
    order = ExecutionOrder("o1", "d1", "XAUUSD", "BUY", 1.0, idempotency_key="d1:XAUUSD")
    assert oms.submit(order).order_id == "o1"
    assert oms.submit(ExecutionOrder("o2", "d1", "XAUUSD", "BUY", 1.0, idempotency_key="d1:XAUUSD")).order_id == "o1"
    oms.transition("o1", OrderStatus.VALIDATED)
    oms.transition("o1", OrderStatus.ROUTING)
    with pytest.raises(ValueError):
        oms.transition("o1", OrderStatus.FILLED)


def test_oms_rejects_conflicting_order_id_identity():
    oms = OrderManager()
    oms.submit(ExecutionOrder("same", "d1", "XAUUSD", "BUY", 1.0, idempotency_key="idem"))
    with pytest.raises(ValueError, match="different order identity"):
        oms.submit(ExecutionOrder("same", "d2", "XAUUSD", "BUY", 1.0, idempotency_key="idem"))


def test_router_prefers_healthy_liquid_venue():
    router = SmartOrderRouter()
    quotes = [VenueQuote("slow", "XAUUSD", 100, 101, 10, 500, 0.8, 0.1, 4), VenueQuote("good", "XAUUSD", 100, 100.5, 20, 20, 0.99, 0.01, 1)]
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


def test_oms_freezes_ambiguous_working_order_for_recovery():
    oms = OrderManager()
    order = oms.submit(ExecutionOrder("recover-1", "d1", "XAUUSD", "BUY", 1))
    oms.transition(order.order_id, OrderStatus.VALIDATED)
    oms.transition(order.order_id, OrderStatus.ROUTING)
    oms.transition(order.order_id, OrderStatus.WORKING)
    recovered = oms.freeze_for_reconciliation(order.order_id)
    assert recovered.status == OrderStatus.RECOVERY_REQUIRED


def test_surveillance_detects_duplicate_and_venue_failure():
    alerts = inspect(rejection_rate=0.0, slippage_bps=0.0, p99_latency_ms=10, duplicate_order_count=1, venue_healthy=False)
    assert {a.code for a in alerts} == {"DUPLICATE_ORDER", "VENUE_UNHEALTHY"}


def test_pretrade_gate_fails_closed_on_exposure_and_venue():
    order = ExecutionOrder("o1", "d1", "XAUUSD", "BUY", 10)
    limits = PreTradeLimits(500, 1000, 500, 100, 5)
    result = evaluate(order, reference_price=100, portfolio_notional=600, symbol_notional=400, daily_loss=10, spread_bps=2, limits=limits, venue_healthy=False)
    assert not result.allowed
    assert "order notional limit" in result.reasons
    assert "portfolio exposure limit" in result.reasons
    assert "venue unhealthy" in result.reasons


def test_pretrade_gate_rejects_non_finite_and_invalid_side():
    order = ExecutionOrder("o1", "d1", "XAUUSD", "HOLD", 1)
    limits = PreTradeLimits(500, 1000, 500, 100, 5)
    result = evaluate(order, reference_price=nan, portfolio_notional=0, symbol_notional=0, daily_loss=0, spread_bps=0, limits=limits)
    assert not result.allowed
    assert "non-finite risk input" in result.reasons
    assert "invalid order side" in result.reasons
    result = evaluate(order, reference_price=100, portfolio_notional=0, symbol_notional=0, daily_loss=0, spread_bps=0, limits=PreTradeLimits(inf, 1000, 500, 100, 5))
    assert not result.allowed
    assert "non-finite risk input" in result.reasons


def test_execution_schedules_are_deterministic_and_conserve_quantity():
    assert sum(twap_schedule(100, 4)) == 100
    assert sum(vwap_schedule(100, [1, 2, 1])) == 100
    assert sum(pov_schedule(100, [20, 20, 20], 0.5)) == 100
    assert adaptive_policy(spread_bps=1, volatility=0.05, fill_probability=0.99, urgency=0.05) == "PASSIVE"


def test_simulated_venue_matches_adapter_contract():
    venue = SimulatedVenue("sim", 100, 100.2, 5)
    quote = venue.quote("XAUUSD")
    assert quote.venue == "sim"
    order = ExecutionOrder("o1", "d1", "XAUUSD", "BUY", 1)
    assert venue.submit(order) == "sim:o1"


def test_oms_fill_is_idempotent_and_conserves_quantity():
    oms = OrderManager()
    order = oms.submit(ExecutionOrder("fill-1", "d1", "XAUUSD", "BUY", 2.0))
    oms.transition(order.order_id, OrderStatus.VALIDATED)
    oms.transition(order.order_id, OrderStatus.ROUTING)
    oms.transition(order.order_id, OrderStatus.WORKING)
    fill = ExecutionFill("f1", order.order_id, "v:o", 1.0, 100.0)
    oms.record_fill(fill)
    oms.record_fill(fill)
    current = oms.get(order.order_id)
    assert current is not None and current.filled_quantity == 1.0 and current.status == OrderStatus.PARTIALLY_FILLED
