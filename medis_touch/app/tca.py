"""Execution-cost analytics: spread, slippage and implementation shortfall."""
from __future__ import annotations

from .execution_models import TCAResult


def _signed(side: str) -> float:
    side = side.upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    return 1.0 if side == "BUY" else -1.0


def calculate_tca(*, order_id: str, side: str, quantity: float, decision_price: float,
                  arrival_price: float, average_fill_price: float | None,
                  spread: float = 0.0, estimated_market_impact: float = 0.0) -> TCAResult:
    if quantity <= 0 or decision_price <= 0 or arrival_price <= 0:
        raise ValueError("quantity and prices must be positive")
    if average_fill_price is None:
        return TCAResult(order_id, decision_price, arrival_price, None, quantity)
    direction = _signed(side)
    slippage = direction * (average_fill_price - arrival_price) * quantity
    spread_cost = abs(spread) * quantity / 2.0
    shortfall = direction * (average_fill_price - decision_price) * quantity
    return TCAResult(
        order_id=order_id,
        decision_price=decision_price,
        arrival_price=arrival_price,
        average_fill_price=average_fill_price,
        quantity=quantity,
        spread_cost=spread_cost,
        slippage_cost=slippage,
        market_impact_cost=max(0.0, estimated_market_impact * quantity),
        implementation_shortfall=shortfall,
    )
