"""Execution-cost research helpers for strategy/venue/regime attribution and stress tests."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionObservation:
    venue: str
    regime: str
    quantity: float
    implementation_shortfall: float
    slippage_bps: float
    market_impact_bps: float
    strategy: str = "unknown"


@dataclass(frozen=True)
class ExecutionCostSummary:
    observations: int
    total_quantity: float
    total_shortfall: float
    average_slippage_bps: float
    average_impact_bps: float


def summarize(observations: list[ExecutionObservation]) -> ExecutionCostSummary:
    if any(o.quantity <= 0 for o in observations):
        raise ValueError("observation quantities must be positive")
    quantity = sum(o.quantity for o in observations)
    if not observations:
        return ExecutionCostSummary(0, 0.0, 0.0, 0.0, 0.0)
    return ExecutionCostSummary(
        observations=len(observations),
        total_quantity=quantity,
        total_shortfall=sum(o.implementation_shortfall for o in observations),
        average_slippage_bps=sum(o.slippage_bps for o in observations) / len(observations),
        average_impact_bps=sum(o.market_impact_bps for o in observations) / len(observations),
    )


def group_by_venue_and_regime(
    observations: list[ExecutionObservation],
) -> dict[tuple[str, str], ExecutionCostSummary]:
    groups: dict[tuple[str, str], list[ExecutionObservation]] = {}
    for observation in observations:
        groups.setdefault((observation.venue, observation.regime), []).append(observation)
    return {key: summarize(value) for key, value in groups.items()}


def group_by_strategy_regime_venue(
    observations: list[ExecutionObservation],
) -> dict[tuple[str, str, str], ExecutionCostSummary]:
    """Attribute execution quality without treating cost as alpha performance."""
    groups: dict[tuple[str, str, str], list[ExecutionObservation]] = {}
    for observation in observations:
        groups.setdefault((observation.strategy, observation.regime, observation.venue), []).append(observation)
    return {key: summarize(value) for key, value in groups.items()}


def stress_shortfall(observation: ExecutionObservation, *, spread_multiplier: float,
                     slippage_multiplier: float, impact_multiplier: float) -> float:
    if min(spread_multiplier, slippage_multiplier, impact_multiplier) < 0:
        raise ValueError("stress multipliers must be non-negative")
    # Baseline shortfall is retained; stress multipliers apply only to execution costs.
    return observation.implementation_shortfall * (
        spread_multiplier + slippage_multiplier + impact_multiplier
    ) / 3.0
