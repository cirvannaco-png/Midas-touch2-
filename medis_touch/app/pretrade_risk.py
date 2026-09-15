"""Fail-closed pre-trade risk gate for the institutional execution path."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from threading import RLock

from .execution_models import ExecutionOrder, RiskDecision


@dataclass(frozen=True)
class PreTradeLimits:
    max_order_notional: float
    max_portfolio_notional: float
    max_symbol_notional: float
    max_daily_loss: float
    max_spread_bps: float


@dataclass(frozen=True)
class RiskReservation:
    reservation_id: str
    portfolio_notional: float
    symbol_notionals: tuple[tuple[str, float], ...]


class RiskReservationBook:
    """Process-local atomic exposure reservation ledger.

    This closes the check-then-submit race among workers sharing one process.
    Multi-process deployments must back this contract with a shared atomic
    database/Redis reservation mechanism; the in-memory implementation is not
    presented as distributed persistence.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._reservations: dict[str, RiskReservation] = {}

    def reserve(
        self,
        reservation_id: str,
        *,
        portfolio_notional: float,
        symbol_notionals: dict[str, float],
        requested_portfolio_notional: float,
        requested_symbol_notionals: dict[str, float],
        limits: PreTradeLimits,
    ) -> RiskReservation:
        if not reservation_id:
            raise ValueError("reservation_id is required")
        with self._lock:
            existing = self._reservations.get(reservation_id)
            if existing is not None:
                return existing
            values = (
                portfolio_notional,
                requested_portfolio_notional,
                *symbol_notionals.values(),
                *requested_symbol_notionals.values(),
            )
            if not all(isfinite(value) and value >= 0 for value in values):
                raise ValueError("risk reservation inputs must be finite and non-negative")
            reserved_portfolio = sum(item.portfolio_notional for item in self._reservations.values())
            if portfolio_notional + reserved_portfolio + requested_portfolio_notional > limits.max_portfolio_notional:
                raise PermissionError("portfolio exposure reservation limit")
            merged = dict(symbol_notionals)
            for item in self._reservations.values():
                for symbol, notional in item.symbol_notionals:
                    merged[symbol] = merged.get(symbol, 0.0) + notional
            for symbol, notional in requested_symbol_notionals.items():
                if merged.get(symbol, 0.0) + notional > limits.max_symbol_notional:
                    raise PermissionError(f"symbol exposure reservation limit: {symbol}")
            reservation = RiskReservation(
                reservation_id=reservation_id,
                portfolio_notional=requested_portfolio_notional,
                symbol_notionals=tuple(sorted(requested_symbol_notionals.items())),
            )
            self._reservations[reservation_id] = reservation
            return reservation

    def release(self, reservation_id: str) -> None:
        with self._lock:
            self._reservations.pop(reservation_id, None)

    def snapshot(self) -> tuple[RiskReservation, ...]:
        with self._lock:
            return tuple(self._reservations.values())


def evaluate(
    order: ExecutionOrder,
    *,
    reference_price: float,
    portfolio_notional: float,
    symbol_notional: float,
    daily_loss: float,
    spread_bps: float,
    limits: PreTradeLimits,
    venue_healthy: bool = True,
    configuration_authorized: bool = True,
) -> RiskDecision:
    reasons: list[str] = []
    numeric_inputs = (
        reference_price,
        portfolio_notional,
        symbol_notional,
        daily_loss,
        spread_bps,
        limits.max_order_notional,
        limits.max_portfolio_notional,
        limits.max_symbol_notional,
        limits.max_daily_loss,
        limits.max_spread_bps,
        order.quantity,
    )
    if not all(isfinite(value) for value in numeric_inputs):
        reasons.append("non-finite risk input")
    if order.quantity <= 0 or reference_price <= 0:
        reasons.append("invalid quantity/reference price")
    if portfolio_notional < 0 or symbol_notional < 0 or daily_loss < 0 or spread_bps < 0:
        reasons.append("invalid negative risk input")
    if any(limit < 0 for limit in (
        limits.max_order_notional,
        limits.max_portfolio_notional,
        limits.max_symbol_notional,
        limits.max_daily_loss,
        limits.max_spread_bps,
    )):
        reasons.append("invalid negative risk limit")
    if order.side.upper() not in {"BUY", "SELL"}:
        reasons.append("invalid order side")
    notional = order.quantity * reference_price
    if notional > limits.max_order_notional:
        reasons.append("order notional limit")
    if portfolio_notional + notional > limits.max_portfolio_notional:
        reasons.append("portfolio exposure limit")
    if symbol_notional + notional > limits.max_symbol_notional:
        reasons.append("symbol exposure limit")
    if daily_loss >= limits.max_daily_loss:
        reasons.append("daily loss limit")
    if spread_bps > limits.max_spread_bps:
        reasons.append("spread limit")
    if not venue_healthy:
        reasons.append("venue unhealthy")
    if not configuration_authorized:
        reasons.append("configuration not authorized")
    return RiskDecision(allowed=not reasons, reasons=tuple(reasons))
