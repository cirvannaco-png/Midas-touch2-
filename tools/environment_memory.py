"""Environment -> Strategy -> Outcome memory analytics.

This module is deliberately observational. It aggregates immutable resolved
outcomes into an environment/strategy matrix and assigns conservative quality
states. It does not modify trading thresholds or promote configurations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from statistics import mean

RESOLVED = {"win", "loss", "scratch"}


@dataclass(frozen=True)
class EnvironmentMemoryEvidence:
    trades: int
    wins: int
    losses: int
    scratches: int
    win_rate: float | None
    win_rate_ci_low: float | None
    win_rate_ci_high: float | None
    expectancy_r: float | None
    profit_factor: float | None
    max_drawdown_r: float | None
    avg_mae_r: float | None
    avg_mfe_r: float | None
    avg_duration: float | None
    status: str


def wilson_interval(wins: int, n: int, confidence: float = 0.95) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    z = 1.959963984540054 if abs(confidence - 0.95) < 1e-9 else 1.959963984540054
    p = wins / n
    den = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    spread = z * sqrt((p * (1.0 - p) / n) + (z * z / (4.0 * n * n)))
    return (centre - spread) / den, (centre + spread) / den


def _quality(evidence: EnvironmentMemoryEvidence, min_sample: int = 30) -> str:
    if evidence.trades < min_sample:
        return "UNKNOWN"
    if (
        evidence.expectancy_r is not None
        and evidence.expectancy_r > 0
        and evidence.profit_factor is not None
        and evidence.profit_factor > 1.0
        and evidence.win_rate_ci_low is not None
        and evidence.win_rate_ci_low >= 0.50
    ):
        return "QUALIFIED"
    if (
        (evidence.expectancy_r is not None and evidence.expectancy_r < 0)
        or (evidence.profit_factor is not None and evidence.profit_factor < 1.0)
        or (evidence.win_rate_ci_high is not None and evidence.win_rate_ci_high < 0.50)
    ):
        return "DEGRADED"
    return "NEUTRAL"


def aggregate(rows, *, min_sample: int = 30) -> dict[tuple, EnvironmentMemoryEvidence]:
    buckets: dict[tuple, list] = {}
    for row in rows:
        if getattr(row, "outcome", None) not in RESOLVED:
            continue
        key = (
            getattr(row, "symbol", None) or "(unknown)",
            getattr(row, "strategy", None) or "STRATEGY_NONE",
            getattr(row, "regime", None) or "REGIME_UNDEFINED",
            getattr(row, "vol_regime", None) or "VOL_REGIME_UNDEFINED",
            getattr(row, "trend_strength_bucket", None),
            getattr(row, "liquidity_bucket", None),
            getattr(row, "news_risk", None) or "NEWS_NONE",
            getattr(row, "session", None) or "SESSION_DEAD",
            getattr(row, "spread_bucket", None),
            getattr(row, "atr_regime", None) or getattr(row, "vol_regime", None),
            getattr(row, "htf_ob_state", None),
            getattr(row, "va_zone", None),
            getattr(row, "market_phase", None),
            getattr(row, "structure_state", None),
        )
        buckets.setdefault(key, []).append(row)

    result: dict[tuple, EnvironmentMemoryEvidence] = {}
    for key, group in buckets.items():
        ordered = sorted(group, key=lambda r: getattr(r, "received_at", None))
        n = len(ordered)
        wins = sum(1 for r in ordered if r.outcome == "win")
        losses = sum(1 for r in ordered if r.outcome == "loss")
        scratches = sum(1 for r in ordered if r.outcome == "scratch")
        r_values = [r.realized_r for r in ordered if r.realized_r is not None]
        gains = sum(v for v in r_values if v > 0)
        loss_abs = abs(sum(v for v in r_values if v < 0))
        cumulative = peak = max_dd = 0.0
        for value in r_values:
            cumulative += value
            peak = max(peak, cumulative)
            max_dd = max(max_dd, peak - cumulative)
        mae = [r.mae_r for r in ordered if r.mae_r is not None]
        mfe = [r.mfe_r for r in ordered if r.mfe_r is not None]
        durations = [r.bars_held for r in ordered if r.bars_held is not None]
        ci_low, ci_high = wilson_interval(wins, wins + losses)
        evidence = EnvironmentMemoryEvidence(
            trades=n,
            wins=wins,
            losses=losses,
            scratches=scratches,
            win_rate=(wins / (wins + losses)) if wins + losses else None,
            win_rate_ci_low=ci_low,
            win_rate_ci_high=ci_high,
            expectancy_r=(mean(r_values) if r_values else None),
            profit_factor=(gains / loss_abs if loss_abs else (float("inf") if gains else None)),
            max_drawdown_r=max_dd if r_values else None,
            avg_mae_r=(mean(mae) if mae else None),
            avg_mfe_r=(mean(mfe) if mfe else None),
            avg_duration=(mean(durations) if durations else None),
            status="UNKNOWN",
        )
        evidence = EnvironmentMemoryEvidence(**{**asdict(evidence), "status": _quality(evidence, min_sample)})
        result[key] = evidence
    return result


def as_report(rows, *, min_sample: int = 30) -> list[dict]:
    matrix = aggregate(rows, min_sample=min_sample)
    output = []
    for key, evidence in matrix.items():
        record = dict(zip(
            [
                "symbol", "strategy", "regime", "vol_regime", "trend_strength_bucket",
                "liquidity_bucket", "news_risk", "session", "spread_bucket", "atr_regime",
                "htf_ob_state", "va_zone", "market_phase", "structure_state",
            ],
            key,
        ))
        record.update(asdict(evidence))
        output.append(record)
    return sorted(output, key=lambda r: (-r["trades"], r["symbol"], r["strategy"], r["regime"]))
