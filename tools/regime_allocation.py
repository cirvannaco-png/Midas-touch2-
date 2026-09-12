"""Statistically gated regime-specific portfolio allocation.

This module deliberately does NOT tune allocations from point estimates alone.
A regime may receive a larger/smaller allocation only when its resolved sample
is large enough, expectancy is positive, drawdown is bounded, and its Wilson
win-rate interval clears the configured floor. Otherwise the previous/default
allocation is retained.

The returned multiplier is a portfolio risk multiplier, not a confidence
multiplier. Raw signal confidence therefore remains untouched and comparable
across calibration cycles.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import NormalDist


@dataclass(frozen=True)
class RegimeAllocationThresholds:
    min_trades: int = 50
    min_avg_r: float = 0.10
    min_win_rate: float = 0.52
    max_drawdown_r: float = 6.0
    confidence: float = 0.95
    min_improvement: float = 0.05
    floor: float = 0.25
    ceiling: float = 1.00
    step: float = 0.10


def _wilson_lower(wins: int, n: int, confidence: float) -> float:
    if n <= 0:
        return 0.0
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    p = wins / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    spread = z * sqrt((p * (1.0 - p) / n) + (z * z / (4.0 * n * n)))
    return (centre - spread) / denom


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def propose_multiplier(metrics: dict, previous: float, thresholds: RegimeAllocationThresholds | None = None) -> tuple[float, str]:
    """Return (new_multiplier, reason).

    `metrics` expects trades, wins, avg_r and max_drawdown_r. Missing or
    non-finite evidence holds the previous allocation. No automatic increase
    occurs merely because win rate is high.
    """
    t = thresholds or RegimeAllocationThresholds()
    previous = _clamp(previous, t.floor, t.ceiling)

    try:
        n = int(metrics.get("trades", 0))
        wins = int(metrics.get("wins", 0))
        avg_r = float(metrics.get("avg_r"))
        max_dd = float(metrics.get("max_drawdown_r"))
    except (TypeError, ValueError):
        return previous, "HOLD: incomplete statistical evidence"

    if n < t.min_trades:
        return previous, f"HOLD: sample {n} < minimum {t.min_trades}"
    if n <= 0 or wins < 0 or wins > n:
        return previous, "HOLD: invalid sample statistics"

    lower_wr = _wilson_lower(wins, n, t.confidence)
    if lower_wr < t.min_win_rate:
        return previous, f"HOLD: Wilson lower win-rate bound {lower_wr:.3f} < {t.min_win_rate:.3f}"
    if avg_r < t.min_avg_r:
        return previous, f"HOLD: avg R {avg_r:.3f} < {t.min_avg_r:.3f}"
    if max_dd > t.max_drawdown_r:
        return previous, f"HOLD: max drawdown {max_dd:.3f}R > {t.max_drawdown_r:.3f}R"

    # Evidence passed. Scale from expectancy quality, but only in discrete
    # steps and never above the configured ceiling. This avoids reacting to
    # tiny cycle-to-cycle noise.
    quality = _clamp(avg_r / max(t.min_avg_r * 3.0, 1e-9), 0.0, 1.0)
    target = t.floor + (t.ceiling - t.floor) * quality
    target = round(target / t.step) * t.step
    target = _clamp(target, t.floor, t.ceiling)

    if abs(target - previous) < t.min_improvement:
        return previous, f"HOLD: proposed change {abs(target - previous):.3f} < minimum {t.min_improvement:.3f}"

    direction = "INCREASE" if target > previous else "DECREASE"
    return target, f"{direction}: statistically qualified regime allocation {previous:.2f} -> {target:.2f}"


def build_regime_allocations(rows, previous: dict[str, float] | None = None,
                             thresholds: RegimeAllocationThresholds | None = None) -> dict:
    """Build conservative regime allocations from resolved outcome rows.

    Rows are expected to expose `regime`, `outcome`, and `realized_r`.
    Missing regimes are ignored. Existing allocations are retained when a
    regime lacks sufficient evidence.
    """
    previous = previous or {}
    t = thresholds or RegimeAllocationThresholds()
    buckets: dict[str, list] = {}
    for row in rows:
        regime = getattr(row, "regime", None) or "REGIME_UNDEFINED"
        outcome = getattr(row, "outcome", None)
        realized_r = getattr(row, "realized_r", None)
        if outcome not in {"win", "loss", "scratch"} or realized_r is None:
            continue
        buckets.setdefault(regime, []).append(row)

    result = {}
    for regime, bucket in buckets.items():
        values = [float(r.realized_r) for r in bucket]
        wins = sum(1 for r in bucket if r.outcome == "win")
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for value in values:
            cumulative += value
            peak = max(peak, cumulative)
            max_dd = max(max_dd, peak - cumulative)
        metrics = {
            "trades": len(bucket),
            "wins": wins,
            "avg_r": sum(values) / len(values),
            "max_drawdown_r": max_dd,
        }
        old = previous.get(regime, 0.50)
        multiplier, reason = propose_multiplier(metrics, old, t)
        result[regime] = {
            "risk_multiplier": multiplier,
            "previous_multiplier": old,
            "metrics": metrics,
            "reason": reason,
            "statistically_qualified": reason.startswith(("INCREASE:", "DECREASE:")),
        }
    return result
