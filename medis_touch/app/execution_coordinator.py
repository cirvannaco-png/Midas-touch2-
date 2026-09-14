"""Governed end-to-end execution coordinator."""

from dataclasses import replace

from .child_execution import ChildOrderExecutor
from .execution_governance import ExecutionConfig, attach_identity, promotion_allowed
from .execution_models import ExecutionFill, ExecutionOrder, ExecutionOutcome, OrderStatus
from .execution_outcome import OutcomeObservation, to_observation
from .execution_router import SmartOrderRouter
from .execution_surveillance import inspect
from .oms import OrderManager
from .pretrade_risk import PreTradeLimits, evaluate
from .reconciliation import reconcile
from .tca import calculate_tca
from .venue import ExecutionVenue


class GovernedExecutionCoordinator:
    """Single path from authorized Midas decision to measured execution outcome."""

    def __init__(self, venue: ExecutionVenue, config: ExecutionConfig, *, approved_hash: str | None, evidence_passed: bool) -> None:
        if not promotion_allowed(challenger=config, approved_hash=approved_hash, evidence_passed=evidence_passed):
            raise PermissionError("execution configuration is not approved")
        self.venue = venue
        self.config = config
        self.oms = OrderManager(require_governance=True)
        self.router = SmartOrderRouter()
        self.children = ChildOrderExecutor()

    def execute(
        self,
        order: ExecutionOrder,
        *,
        reference_price: float,
        portfolio_notional: float,
        symbol_notional: float,
        daily_loss: float,
        spread_bps: float,
        limits: PreTradeLimits,
        regime: str,
        observed_volumes: list[float] | None = None,
    ) -> tuple[ExecutionOutcome, OutcomeObservation]:
        existing_hash = order.metadata.get("execution_config_hash")
        if existing_hash is not None and existing_hash != self.config.config_hash:
            raise PermissionError("order execution configuration hash does not match approved configuration")
        governed = ExecutionOrder(**{**order.__dict__, "metadata": attach_identity(order.metadata, self.config)})
        quote = self.venue.quote(governed.symbol)
        if quote.symbol != governed.symbol:
            raise RuntimeError("venue returned a quote for the wrong symbol")
        if quote.venue not in self.config.allowed_venues:
            raise PermissionError("quoted venue is not authorized by execution configuration")
        if not quote.healthy:
            raise PermissionError("execution venue is unhealthy")
        risk = evaluate(
            governed, reference_price=reference_price, portfolio_notional=portfolio_notional,
            symbol_notional=symbol_notional, daily_loss=daily_loss, spread_bps=spread_bps,
            limits=limits, venue_healthy=quote.healthy, configuration_authorized=True,
        )
        if not risk.allowed:
            raise PermissionError("pre-trade risk rejected: " + "; ".join(risk.reasons))

        stored = self.oms.submit(governed)
        self.oms.transition(stored.order_id, OrderStatus.VALIDATED)
        route = self.router.route([quote], stored.quantity)
        if route.venue not in self.config.allowed_venues:
            raise PermissionError("router selected an unauthorized venue")
        self.oms.transition(stored.order_id, OrderStatus.ROUTING)
        children = self.children.build_children(stored, observed_volumes=observed_volumes)
        self.oms.transition(stored.order_id, OrderStatus.WORKING)

        child_reconciliations = []
        try:
            for child in children:
                child = replace(child, venue=route.venue, status=OrderStatus.WORKING)
                venue_order_id = self.venue.submit(child)
                fill_price = quote.ask if child.side.upper() == "BUY" else quote.bid
                fill = self.venue.fill(child, venue_order_id, fill_price)
                self.oms.record_fill(
                    ExecutionFill(fill.fill_id, stored.order_id, venue_order_id,
                                  fill.quantity, fill.price, fill.timestamp)
                )
                expected_child = replace(
                    child, status=OrderStatus.FILLED,
                    filled_quantity=child.quantity,
                    average_fill_price=fill.price,
                )
                observed = self.venue.reconcile(venue_order_id)
                observed_status = OrderStatus(observed.get("status", "UNKNOWN"))
                child_reconciliations.append(reconcile(expected_child, observed_status, fill.quantity))
        except Exception:
            self.oms.freeze_for_reconciliation(stored.order_id)
            raise

        current = self.oms.get(stored.order_id)
        assert current is not None
        reconciled = all(result.matched for result in child_reconciliations)
        if not reconciled:
            self.oms.freeze_for_reconciliation(current.order_id)
            current = self.oms.get(current.order_id)
            assert current is not None

        alerts = inspect(
            rejection_rate=quote.rejection_rate, slippage_bps=quote.historical_slippage_bps,
            p99_latency_ms=quote.latency_ms, venue_healthy=quote.healthy,
        )
        tca = calculate_tca(
            order_id=current.order_id, side=current.side, quantity=current.quantity,
            decision_price=reference_price,
            arrival_price=quote.ask if current.side.upper() == "BUY" else quote.bid,
            average_fill_price=current.average_fill_price, spread=quote.spread,
        )
        outcome = ExecutionOutcome(
            order_id=current.order_id, decision_id=current.decision_id, symbol=current.symbol,
            side=current.side, requested_quantity=current.quantity, filled_quantity=current.filled_quantity,
            average_fill_price=current.average_fill_price, status=current.status, tca=tca,
            execution_config_hash=self.config.config_hash, execution_model_hash=self.config.model_hash,
            reconciled=reconciled, surveillance_codes=tuple(a.code for a in alerts),
        )
        return outcome, to_observation(outcome, regime=regime, policy=route.policy.value, venue=route.venue)
