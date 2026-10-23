"""Paired challenger statistics for identical market opportunities.

Use a two-sided Student-t test on paired deltas, with the exact Student-t
tail probability computed through the regularized incomplete beta function.
This avoids the anti-conservative normal-tail approximation at small sample
sizes. Statistical significance is diagnostic only; it is not a promotion
signal and does not replace locked out-of-sample validation.
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


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the continued fraction for the incomplete beta function."""
    max_iterations = 300
    epsilon = 3.0e-14
    tiny = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) <= epsilon:
            return h
    raise ArithmeticError("incomplete-beta continued fraction did not converge")


def _regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """Return I_x(a,b), the regularized incomplete beta function."""
    if a <= 0.0 or b <= 0.0 or not 0.0 <= x <= 1.0:
        raise ValueError("beta parameters must be positive and x must be in [0, 1]")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        result = bt * _beta_continued_fraction(a, b, x) / a
    else:
        result = 1.0 - bt * _beta_continued_fraction(b, a, 1.0 - x) / b
    return min(1.0, max(0.0, result))


def _student_t_two_sided_p(t_statistic: float, degrees_freedom: int) -> float:
    """Exact two-sided Student-t tail probability for finite t and df."""
    if degrees_freedom < 1:
        raise ValueError("degrees of freedom must be positive")
    if math.isnan(t_statistic):
        raise ValueError("t statistic cannot be NaN")
    if math.isinf(t_statistic):
        return 0.0
    x = degrees_freedom / (degrees_freedom + t_statistic * t_statistic)
    return _regularized_incomplete_beta(degrees_freedom / 2.0, 0.5, x)


def paired_mean_test(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    alpha: float = 0.05,
) -> PairedTestResult:
    """Compare aligned paired outcomes using a two-sided paired Student-t test.

    Candidate improvement is considered statistically significant only when
    the two-sided p-value is below alpha and the mean paired delta is positive.
    Constant paired deltas have zero estimated variance, so their p-value is
    conservatively set to 1 rather than claiming certainty from a degenerate
    variance estimate.
    """
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
        # Retain the signed infinite ratio for compatibility, but do not
        # infer significance from a variance estimate of exactly zero.
        t_statistic = math.inf if avg > 0.0 else -math.inf if avg < 0.0 else 0.0
        p_value = 1.0
    else:
        t_statistic = avg / se
        p_value = _student_t_two_sided_p(t_statistic, n - 1)
    return PairedTestResult(
        n=n,
        mean_delta=avg,
        standard_error=se,
        t_statistic=t_statistic,
        p_value=p_value,
        significant=p_value < alpha and avg > 0.0,
    )
