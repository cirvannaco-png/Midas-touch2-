"""Multiple-testing correction for bounded research candidate searches.

This is a pure-Python port of Medis Touch's Holm step-down correction.
It returns results in original input order, so callers can safely align
adjusted p-values with candidate IDs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence


@dataclass(frozen=True)
class AdjustedPValue:
    index: int
    raw_p: float
    adjusted_p: float
    reject: bool


def holm_bonferroni(p_values: Sequence[float], *, alpha: float = 0.05) -> list[AdjustedPValue]:
    """Apply Holm's family-wise-error step-down adjustment.

    The adjusted p-values are monotone in sorted p-value order. Hypotheses
    are rejected only when the adjusted p-value is strictly below alpha,
    matching the source package's decision boundary.
    """
    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be finite and in (0, 1)")
    values = [float(p) for p in p_values]
    if any(not math.isfinite(p) or not 0.0 <= p <= 1.0 for p in values):
        raise ValueError("p-values must be finite and in [0, 1]")

    ranked = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    adjusted: dict[int, float] = {}
    running = 0.0
    count = len(values)
    for rank, (index, p_value) in enumerate(ranked):
        value = min(1.0, (count - rank) * p_value)
        running = max(running, value)
        adjusted[index] = running

    return [
        AdjustedPValue(index, p_value, adjusted[index], adjusted[index] < alpha)
        for index, p_value in enumerate(values)
    ]
