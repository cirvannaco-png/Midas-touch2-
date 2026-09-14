"""Fail-closed pre-trade risk gate for the institutional execution path."""
from __future__ import annotations

from dataclasses import dataclass

from .execution_models import ExecutionOrder, RiskDecision


@dataclass(frozen=True)
class PreTradeLimits:
    max_order_notional: float
    max_portfolio_notional: float
    max_symbol_notional: float
    max_daily_loss: float
    max_spread_bps: float


def evaluate(order: ExecutionOrder, *, reference_price: float, portfolio_notional: float,
             symbol_notional: float, daily_loss: float, spread_bps: float,
             limits: PreTradeLimits, venue_healthy: bool = True,
             configuration_authorized: bool = True) -> RiskDecision:
    reasons: list[str] = []
    if order.quantity <= 0 or reference_price <= 0:
        reasons.append("invalid quantity/reference price")
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
