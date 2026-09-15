"""Lightweight model/data drift monitoring for Midas.

No third-party numerical dependency is required. The metrics are intended as
production guardrails rather than as a replacement for full offline research.
"""
from __future__ import annotations

from math import log
from statistics import mean


def _normalize(values: list[float], bins: int) -> list[float]:
    if not values:
        raise ValueError("values must not be empty")
    lo, hi = min(values), max(values)
    if lo == hi:
        return [1.0] + [0.0] * (bins - 1)
    counts = [0] * bins
    width = (hi - lo) / bins
    for value in values:
        index = min(bins - 1, int((value - lo) / width))
        counts[index] += 1
    total = len(values)
    return [count / total for count in counts]


def population_stability_index(reference: list[float], current: list[float], bins: int = 10) -> float:
    """Calculate PSI using common min/max bounds and epsilon protection."""
    if not reference or not current:
        raise ValueError("reference and current must not be empty")
    if bins < 2:
        raise ValueError("bins must be >= 2")
    lo, hi = min(reference + current), max(reference + current)
    if lo == hi:
        return 0.0
    width = (hi - lo) / bins

    def distribution(values: list[float]) -> list[float]:
        counts = [0] * bins
        for value in values:
            index = min(bins - 1, int((value - lo) / width))
            counts[index] += 1
        n = len(values)
        return [max(count / n, 1e-9) for count in counts]

    ref = distribution(reference)
    cur = distribution(current)
    return sum((c - r) * log(c / r) for r, c in zip(ref, cur))


def jensen_shannon_divergence(reference: list[float], current: list[float]) -> float:
    """JSD for already-normalized discrete distributions."""
    if len(reference) != len(current) or not reference:
        raise ValueError("distributions must have equal non-zero length")
    if any(value < 0 for value in reference + current):
        raise ValueError("distribution values must be non-negative")
    if abs(sum(reference) - 1.0) > 1e-6 or abs(sum(current) - 1.0) > 1e-6:
        raise ValueError("distributions must sum to 1")

    def kl(p: list[float], q: list[float]) -> float:
        return sum(value * log(value / max(other, 1e-12)) for value, other in zip(p, q) if value > 0)

    midpoint = [(a + b) / 2 for a, b in zip(reference, current)]
    return 0.5 * kl(reference, midpoint) + 0.5 * kl(current, midpoint)


def calibration_error(predicted: list[float], observed: list[float]) -> float:
    """Mean absolute calibration error for paired probability/outcome data."""
    if len(predicted) != len(observed) or not predicted:
        raise ValueError("predicted and observed must have equal non-zero length")
    if any(not 0 <= p <= 1 for p in predicted):
        raise ValueError("predicted probabilities must be in [0, 1]")
    if any(o not in (0, 1) for o in observed):
        raise ValueError("observed outcomes must be 0 or 1")
    return mean(abs(p - o) for p, o in zip(predicted, observed))


def drift_state(psi: float, *, watch: float = 0.10, restrict: float = 0.25) -> str:
    if psi < watch:
        return "NORMAL"
    if psi < restrict:
        return "WATCH"
    return "RESTRICT"
