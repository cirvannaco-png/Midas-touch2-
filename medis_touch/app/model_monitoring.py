"""Lightweight model/data drift monitoring for Midas.

No third-party numerical dependency is required. The metrics are intended as
production guardrails rather than as a replacement for full offline research.
"""
from __future__ import annotations

from math import isfinite, log
from statistics import mean


def _validate_finite(values: list[float], name: str) -> None:
    if not values or not all(isfinite(value) for value in values):
        raise ValueError(f"{name} must contain finite values")


def _normalize(values: list[float], bins: int) -> list[float]:
    _validate_finite(values, "values")
    if bins < 2:
        raise ValueError("bins must be >= 2")
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
    _validate_finite(reference, "reference")
    _validate_finite(current, "current")
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
    if any(not isfinite(value) or value < 0 for value in reference + current):
        raise ValueError("distribution values must be finite and non-negative")
    if abs(sum(reference) - 1.0) > 1e-6 or abs(sum(current) - 1.0) > 1e-6:
        raise ValueError("distributions must sum to 1")

    def kl(p: list[float], q: list[float]) -> float:
        return sum(value * log(value / max(other, 1e-12)) for value, other in zip(p, q) if value > 0)

    midpoint = [(a + b) / 2 for a, b in zip(reference, current)]
    return 0.5 * kl(reference, midpoint) + 0.5 * kl(current, midpoint)


def calibration_error(predicted: list[float], observed: list[float]) -> float:
    """Mean absolute error between predicted probabilities and binary outcomes."""
    if len(predicted) != len(observed) or not predicted:
        raise ValueError("predicted and observed must have equal non-zero length")
    if any(not isfinite(p) or not 0 <= p <= 1 for p in predicted):
        raise ValueError("predicted probabilities must be finite and in [0, 1]")
    if any(o not in (0, 1) for o in observed):
        raise ValueError("observed outcomes must be 0 or 1")
    return mean(abs(p - o) for p, o in zip(predicted, observed))


def expected_calibration_error(predicted: list[float], observed: list[int], bins: int = 10) -> float:
    """Bucketed ECE: weighted gap between mean confidence and empirical accuracy."""
    if len(predicted) != len(observed) or not predicted:
        raise ValueError("predicted and observed must have equal non-zero length")
    if bins < 2:
        raise ValueError("bins must be >= 2")
    if any(not isfinite(p) or not 0 <= p <= 1 for p in predicted):
        raise ValueError("predicted probabilities must be finite and in [0, 1]")
    if any(o not in (0, 1) for o in observed):
        raise ValueError("observed outcomes must be 0 or 1")
    buckets = [[] for _ in range(bins)]
    for probability, outcome in zip(predicted, observed):
        buckets[min(bins - 1, int(probability * bins))].append((probability, outcome))
    total = len(predicted)
    return sum((len(bucket) / total) * abs(mean(p for p, _ in bucket) - mean(o for _, o in bucket)) for bucket in buckets if bucket)


def brier_score(predicted: list[float], observed: list[int]) -> float:
    """Mean squared probability error; lower is better."""
    if len(predicted) != len(observed) or not predicted:
        raise ValueError("predicted and observed must have equal non-zero length")
    if any(not isfinite(p) or not 0 <= p <= 1 for p in predicted):
        raise ValueError("predicted probabilities must be finite and in [0, 1]")
    if any(o not in (0, 1) for o in observed):
        raise ValueError("observed outcomes must be 0 or 1")
    return mean((p - o) ** 2 for p, o in zip(predicted, observed))


def drift_state(psi: float, *, watch: float = 0.10, restrict: float = 0.25) -> str:
    if not all(isfinite(value) for value in (psi, watch, restrict)):
        raise ValueError("drift thresholds must be finite")
    if watch < 0 or restrict <= watch:
        raise ValueError("require 0 <= watch < restrict")
    if psi < 0:
        raise ValueError("PSI cannot be negative")
    if psi < watch:
        return "NORMAL"
    if psi < restrict:
        return "WATCH"
    return "RESTRICT"
