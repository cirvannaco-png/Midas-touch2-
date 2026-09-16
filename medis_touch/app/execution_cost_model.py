"""Execution-cost model used by backtests without future-data leakage."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostAssumptions:
    commission_per_unit: float = 0.0
    spread_fraction: float = 0.5
    slippage_bps: float = 0.0
    impact_bps_per_participation: float = 0.0


def estimate_execution_cost(
    *,
    quantity: float,
    reference_price: float,
    spread: float,
    participation: float,
    assumptions: CostAssumptions,
) -> float:
    """Estimate cost from information available at decision/execution time."""
    if quantity <= 0 or reference_price <= 0 or spread < 0:
        raise ValueError("invalid execution-cost inputs")
    if participation < 0 or participation > 1:
        raise ValueError("participation must be in [0, 1]")
    spread_cost = quantity * spread * assumptions.spread_fraction
    slippage_cost = quantity * reference_price * assumptions.slippage_bps / 10_000.0
    impact_cost = quantity * reference_price * assumptions.impact_bps_per_participation * participation / 10_000.0
    commission = quantity * assumptions.commission_per_unit
    return spread_cost + slippage_cost + impact_cost + commission
