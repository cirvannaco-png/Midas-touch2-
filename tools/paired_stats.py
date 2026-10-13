"""Paired challenger statistics for identical market opportunities.

This preserves Medis Touch's paired-mean statistic and normal-tail p-value
approximation so existing experiment outputs remain comparable. It is not
an exact small-sample Student-t test; use adequate sample sizes and treat
the p-value as an approximation when making promotion decisions.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean, stdev


@dataclass(frozen=True)
class PairedTestResult:
    n: int
    mean_delta: float
    standard_error: float
    t_statistic: float
    p_value: float
    significant: bool


def _normal_two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def paired_mean_test(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    alpha: float = 0.05,
) -> PairedTestResult:
    """Compare aligned paired outcomes; candidate must improve to be significant."""
    if len(baseline) != len(candidate):
        raise ValueError("paired samples must have equal length")
    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be finite and in (0, 1)")

    base = [float(value) for value in baseline]
    challenger = [float(value) for value in candidate]
    if any(not math.isfinite(value) for value in (*base, *challenger)):
        raise ValueError("paired observations must be finite")
    deltas = [c - b for b, c in zip(base, challenger, strict=True)]
    n = len(deltas)
    if n < 2:
        raise ValueError("at least two paired observations are required")

    avg = mean(deltas)
    sd = stdev(deltas)
    se = sd / math.sqrt(n)
    if se == 0.0:
        p_value = 0.0 if avg != 0.0 else 1.0
        t_statistic = math.inf if avg > 0.0 else -math.inf if avg < 0.0 else 0.0
    else:
        t_statistic = avg / se
        p_value = _normal_two_sided_p(t_statistic)
    return PairedTestResult(
        n=n,
        mean_delta=avg,
        standard_error=se,
        t_statistic=t_statistic,
        p_value=p_value,
        significant=p_value < alpha and avg > 0.0,
    )
