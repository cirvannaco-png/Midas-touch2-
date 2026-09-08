"""Bounded, deterministic numeric parameter proposal engine.

This module proposes *candidate configurations*; it never decides that a
candidate is profitable and never mutates live EA configuration. Evaluation
must happen through the recalibration guard before promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from itertools import product
from typing import Mapping


@dataclass(frozen=True)
class ParameterBound:
    """Allowed numeric range and step for one optimizable parameter."""

    minimum: float
    maximum: float
    step: float

    def __post_init__(self) -> None:
        if self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        if self.step <= 0:
            raise ValueError("step must be positive")


@dataclass(frozen=True)
class SearchBudget:
    """Hard cap on generated candidates for one recalibration search."""

    max_candidates: int

    def __post_init__(self) -> None:
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be positive")


def _quantize(value: float, step: float) -> float:
    precision = max(0, len(str(step).partition(".")[2].rstrip("0")))
    quantum = Decimal(1).scaleb(-precision)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def bounded_values(center: float, bound: ParameterBound, radius: int = 1) -> tuple[float, ...]:
    """Return center +/- radius steps, clipped to the declared bounds."""
    if radius < 0:
        raise ValueError("radius cannot be negative")
    values = {
        _quantize(
            min(bound.maximum, max(bound.minimum, center + offset * bound.step)),
            bound.step,
        )
        for offset in range(-radius, radius + 1)
    }
    return tuple(sorted(values))


def propose_neighbors(
    baseline: Mapping[str, float],
    bounds: Mapping[str, ParameterBound],
    *,
    radius: int = 1,
    budget: SearchBudget,
) -> tuple[dict[str, float], ...]:
    """Generate a deterministic neighborhood around a baseline.

    Parameters are emitted in sorted-key order. The baseline itself is
    included when it lies within every declared bound. Generation is capped
    before materializing an unbounded Cartesian product.
    """
    if set(baseline) != set(bounds):
        missing = sorted(set(bounds) - set(baseline))
        extra = sorted(set(baseline) - set(bounds))
        raise ValueError(f"baseline/bounds mismatch: missing={missing}, extra={extra}")

    keys = tuple(sorted(bounds))
    value_sets = []
    for key in keys:
        bound = bounds[key]
        center = baseline[key]
        if not bound.minimum <= center <= bound.maximum:
            raise ValueError(f"baseline parameter {key!r} is outside its bounds")
        value_sets.append(bounded_values(center, bound, radius))

    candidates: list[dict[str, float]] = []
    for values in product(*value_sets):
        candidates.append(dict(zip(keys, values, strict=True)))
        if len(candidates) >= budget.max_candidates:
            break
    return tuple(candidates)


def bounded_delta(
    baseline: Mapping[str, float],
    deltas: Mapping[str, float],
    bounds: Mapping[str, ParameterBound],
) -> dict[str, float]:
    """Apply bounded numeric deltas once; intended for a single proposal."""
    if set(baseline) != set(deltas) or set(baseline) != set(bounds):
        raise ValueError("baseline, deltas and bounds must contain identical keys")

    result: dict[str, float] = {}
    for key in sorted(baseline):
        bound = bounds[key]
        value = baseline[key] + deltas[key]
        if not bound.minimum <= value <= bound.maximum:
            raise ValueError(f"proposal for {key!r} exceeds declared bounds")
        result[key] = _quantize(value, bound.step)
    return result
