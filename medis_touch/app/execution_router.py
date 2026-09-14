"""Venue scoring and execution-policy selection."""
from __future__ import annotations

from dataclasses import dataclass

from .execution_models import ExecutionPolicy, VenueQuote


@dataclass(frozen=True)
class RoutingDecision:
    venue: str
    policy: ExecutionPolicy
    score: float
    reasons: tuple[str, ...]


class SmartOrderRouter:
    """Broker/venue-neutral router.

    Lower estimated cost and healthier execution characteristics score higher.
    No route is returned for unhealthy or non-positive-liquidity venues.
    """

    def __init__(self, min_fill_rate: float = 0.50, max_rejection_rate: float = 0.20) -> None:
        self.min_fill_rate = min_fill_rate
        self.max_rejection_rate = max_rejection_rate

    def _score(self, quote: VenueQuote, quantity: float, urgency: float) -> float:
        if not quote.healthy or quote.available_volume <= 0:
            return float("-inf")
        if quote.fill_rate < self.min_fill_rate or quote.rejection_rate > self.max_rejection_rate:
            return float("-inf")
        coverage = min(1.0, quote.available_volume / max(quantity, 1e-12))
        spread_bps = quote.spread / max(quote.bid, 1e-12) * 10_000
        cost = spread_bps + quote.historical_slippage_bps + quote.latency_ms * (0.02 + 0.08 * urgency)
        reliability = quote.fill_rate * (1.0 - quote.rejection_rate)
        return (100.0 * coverage * reliability) - cost

    def route(self, quotes: list[VenueQuote], quantity: float, urgency: float = 0.5) -> RoutingDecision:
        if not quotes or quantity <= 0:
            raise ValueError("quotes and positive quantity are required")
        ranked = sorted(((self._score(q, quantity, urgency), q) for q in quotes), key=lambda x: x[0], reverse=True)
        score, quote = ranked[0]
        if score == float("-inf"):
            raise RuntimeError("no eligible execution venue")
        policy = ExecutionPolicy.MARKET if urgency >= 0.85 else ExecutionPolicy.ADAPTIVE
        return RoutingDecision(
            venue=quote.venue,
            policy=policy,
            score=score,
            reasons=("liquidity coverage", "fill reliability", "spread/slippage", "latency"),
        )
