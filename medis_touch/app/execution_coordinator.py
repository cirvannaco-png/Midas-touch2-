"""Governed end-to-end execution coordinator."""

from dataclasses import replace

from .child_execution import ChildOrderExecutor
from .execution_governance import ExecutionConfig, attach_identity, promotion_allowed
from .execution_models import ExecutionFill, ExecutionOrder, ExecutionOutcome, OrderStatus
from .execution_outcome import OutcomeObservation, to_observation
from .execution_router import SmartOrderRouter
from .execution_surveillance import inspect
from .oms import OrderManager
from .pretrade_risk import PersistentPortfolioAdmission, PreTradeLimits, RiskReservationBook, evaluate
from .reconciliation import reconcile
from .tca import calculate_tca
from .venue import ExecutionVenue


class GovernedExecutionCoordinator:
    """Single path from authorized Midas decision to measured execution outcome."""

    def __init__(self, venue: ExecutionVenue, config: ExecutionConfig, *, approved_hash: str | None, evidence_passed: bool, portfolio_admission: PersistentPortfolioAdmission | None = None, admission_scope: str = "default") -> None:
        if not promotion_allowed(challenger=config, approved_hash=approved_hash, evidence_passed=evidence_passed):
            raise PermissionError("execution configuration is not approved")
        if not admission_scope:
            raise ValueError("admission_scope is required")
        self.venue = venue
        self.config = config
        self.oms = OrderManager(require_governance=True)
        self.router = SmartOrderRouter()
        self.children = ChildOrderExecutor()
        self.portfolio_admission = portfolio_admission
        self.admission_scope = admission_scope
        self._local_reservations = RiskReservationBook()

    def execute_many(self, orders: list[ExecutionOrder] | tuple[ExecutionOrder, ...], *, reference_prices: dict[str, float], portfolio_notional: float, symbol_notionals: dict[str, float], daily_loss: float, spread_bps: dict[str, float], limits: PreTradeLimits, regime: str, observed_volumes: dict[str, list[float]] | None = None) -> tuple[tuple[ExecutionOutcome, OutcomeObservation], ...]:
        """Execute multiple already-authorized trades without bypassing shared risk."""
        batch = tuple(orders)
        if not batch:
            return ()
        seen_ids: set[str] = set()
        seen_idempotency: set[str] = set()
        projected_portfolio = portfolio_notional
        projected_symbols = dict(symbol_notionals)
        for order in batch:
            if order.order_id in seen_ids:
                raise ValueError("duplicate order_id in execution batch")
            seen_ids.add(order.order_id)
            if order.idempotency_key and order.idempotency_key in seen_idempotency:
                raise ValueError("duplicate idempotency key in execution batch")
            if order.idempotency_key:
                seen_idempotency.add(order.idempotency_key)
            reference_price = reference_prices.get(order.symbol)
            spread = spread_bps.get(order.symbol)
            if reference_price is None or spread is None:
                raise ValueError(f"missing execution market inputs for {order.symbol}")
            quote = self.venue.quote(order.symbol)
            if quote.symbol != order.symbol or quote.venue not in self.config.allowed_venues or not quote.healthy:
                raise PermissionError(f"venue is not authorized and healthy for {order.symbol}")
            governed = ExecutionOrder(**{**order.__dict__, "metadata": attach_identity(order.metadata, self.config)})
            risk = evaluate(governed, reference_price=reference_price, portfolio_notional=projected_portfolio, symbol_notional=projected_symbols.get(order.symbol, 0.0), daily_loss=daily_loss, spread_bps=spread, limits=limits, venue_healthy=quote.healthy, configuration_authorized=True)
            if not risk.allowed:
                raise PermissionError(f"batch pre-trade risk rejected {order.order_id}: " + "; ".join(risk.reasons))
            notional = order.quantity * reference_price
            projected_portfolio += notional
            projected_symbols[order.symbol] = projected_symbols.get(order.symbol, 0.0) + notional
        results = []
        projected_portfolio = portfolio_notional
        projected_symbols = dict(symbol_notionals)
        for order in batch:
            result = self.execute(order, reference_price=reference_prices[order.symbol], portfolio_notional=projected_portfolio, symbol_notional=projected_symbols.get(order.symbol, 0.0), daily_loss=daily_loss, spread_bps=spread_bps[order.symbol], limits=limits, regime=regime, observed_volumes=(observed_volumes or {}).get(order.symbol))
            results.append(result)
            notional = order.quantity * reference_prices[order.symbol]
            projected_portfolio += notional
            projected_symbols[order.symbol] = projected_symbols.get(order.symbol, 0.0) + notional
        return tuple(results)

    def _reserve(self, order: ExecutionOrder, *, reference_price: float, portfolio_notional: float, symbol_notional: float, limits: PreTradeLimits):
        requested = order.quantity * reference_price
        if self.portfolio_admission is not None:
            return self.portfolio_admission.reserve(order.order_id, scope_id=self.admission_scope, requested_portfolio_notional=requested, requested_symbol_notionals={order.symbol: requested}, limits=limits)
        return self._local_reservations.reserve(order.order_id, portfolio_notional=portfolio_notional, symbol_notionals={order.symbol: symbol_notional}, requested_portfolio_notional=requested, requested_symbol_notionals={order.symbol: requested}, limits=limits)

    def _commit_reservation(self, order_id: str, *, filled_quantity: float, average_fill_price: float | None, symbol: str) -> None:
        if self.portfolio_admission is None:
            self._local_reservations.consume(order_id)
            return
        filled_notional = 0.0 if average_fill_price is None else filled_quantity * average_fill_price
        self.portfolio_admission.commit(order_id, committed_portfolio_notional=filled_notional, committed_symbol_notionals={symbol: filled_notional})

    def _release_reservation(self, order_id: str) -> None:
        if self.portfolio_admission is None:
            self._local_reservations.release(order_id)
        else:
            self.portfolio_admission.release(order_id)

    def execute(self, order: ExecutionOrder, *, reference_price: float, portfolio_notional: float, symbol_notional: float, daily_loss: float, spread_bps: float, limits: PreTradeLimits, regime: str, observed_volumes: list[float] | None = None) -> tuple[ExecutionOutcome, OutcomeObservation]:
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
        risk = evaluate(governed, reference_price=reference_price, portfolio_notional=portfolio_notional, symbol_notional=symbol_notional, daily_loss=daily_loss, spread_bps=spread_bps, limits=limits, venue_healthy=quote.healthy, configuration_authorized=True)
        if not risk.allowed:
            raise PermissionError("pre-trade risk rejected: " + "; ".join(risk.reasons))
        self._reserve(governed, reference_price=reference_price, portfolio_notional=portfolio_notional, symbol_notional=symbol_notional, limits=limits)
        broker_call_started = False
        try:
            stored = self.oms.submit(governed)
            self.oms.transition(stored.order_id, OrderStatus.VALIDATED)
            route = self.router.route([quote], stored.quantity)
            if route.venue not in self.config.allowed_venues:
                raise PermissionError("router selected an unauthorized venue")
            self.oms.transition(stored.order_id, OrderStatus.ROUTING)
            children = self.children.build_children(stored, observed_volumes=observed_volumes)
            self.oms.transition(stored.order_id, OrderStatus.WORKING)
            child_reconciliations = []
            for child in children:
                child = replace(child, venue=route.venue, status=OrderStatus.WORKING)
                # The submit call itself may have an ambiguous acknowledgement.
                # Mark the external boundary before invoking it so a timeout or
                # transport error cannot release exposure reservation prematurely.
                broker_call_started = True
                venue_order_id = self.venue.submit(child)
                fill_price = quote.ask if child.side.upper() == "BUY" else quote.bid
                fill = self.venue.fill(child, venue_order_id, fill_price)
                self.oms.record_fill(ExecutionFill(fill.fill_id, stored.order_id, venue_order_id, fill.quantity, fill.price, fill.timestamp))
                expected_child = replace(child, status=OrderStatus.FILLED, filled_quantity=child.quantity, average_fill_price=fill.price)
                observed = self.venue.reconcile(venue_order_id)
                observed_status = OrderStatus(observed.get("status", "UNKNOWN"))
                child_reconciliations.append(reconcile(expected_child, observed_status, fill.quantity))
        except Exception:
            if 'stored' in locals():
                self.oms.freeze_for_reconciliation(stored.order_id)
            if not broker_call_started:
                self._release_reservation(governed.order_id)
            raise
        current = self.oms.get(stored.order_id)
        if current is None:
            raise RuntimeError("OMS lost parent order after broker execution")
        reconciled = all(result.matched for result in child_reconciliations)
        if not reconciled:
            self.oms.freeze_for_reconciliation(current.order_id)
            current = self.oms.get(current.order_id)
            if current is None:
                raise RuntimeError("OMS lost parent order during reconciliation recovery")
            raise RuntimeError(f"execution reconciliation unresolved for {current.order_id}")
        self._commit_reservation(current.order_id, filled_quantity=current.filled_quantity, average_fill_price=current.average_fill_price, symbol=current.symbol)
        alerts = inspect(rejection_rate=quote.rejection_rate, slippage_bps=quote.historical_slippage_bps, p99_latency_ms=quote.latency_ms, venue_healthy=quote.healthy)
        tca = calculate_tca(order_id=current.order_id, side=current.side, quantity=current.quantity, decision_price=reference_price, arrival_price=quote.ask if current.side.upper() == "BUY" else quote.bid, average_fill_price=current.average_fill_price, spread=quote.spread)
        outcome = ExecutionOutcome(order_id=current.order_id, decision_id=current.decision_id, symbol=current.symbol, side=current.side, requested_quantity=current.quantity, filled_quantity=current.filled_quantity, average_fill_price=current.average_fill_price, status=current.status, tca=tca, execution_config_hash=self.config.config_hash, execution_model_hash=self.config.model_hash, reconciled=reconciled, surveillance_codes=tuple(a.code for a in alerts))
        return outcome, to_observation(outcome, regime=regime, policy=route.policy.value, venue=route.venue)
