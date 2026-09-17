"""Environment -> Strategy -> Outcome memory analytics.

Historical evidence is advisory only. It cannot bypass setup validation,
risk, portfolio, news, or broker execution gates.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from math import inf, sqrt
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
    adjustment: float = 0.0


def wilson_interval(wins: int, n: int, confidence: float = 0.95) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    z = 1.959963984540054
    if abs(confidence - 0.95) > 1e-9:
        raise ValueError("only 95% Wilson intervals are supported")
    p = wins / n
    den = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    spread = z * sqrt((p * (1.0 - p) / n) + (z * z / (4.0 * n * n)))
    return (centre - spread) / den, (centre + spread) / den


def _quality(evidence: EnvironmentMemoryEvidence, min_sample: int = 30) -> str:
    if evidence.trades == 0 or evidence.win_rate_ci_low is None:
        return "UNKNOWN"
    if evidence.trades >= min_sample and evidence.expectancy_r is not None and evidence.expectancy_r > 0 and evidence.profit_factor is not None and evidence.profit_factor > 1.0 and evidence.win_rate_ci_low >= 0.50:
        return "QUALIFIED"
    if evidence.trades >= (2 * min_sample) and evidence.expectancy_r is not None and evidence.expectancy_r < 0 and evidence.profit_factor is not None and 0.0 <= evidence.profit_factor < 1.0 and evidence.win_rate_ci_high is not None and evidence.win_rate_ci_high < 0.50:
        return "DEGRADED"
    return "NEUTRAL"


def _env(row, key: str):
    environment = getattr(row, "environment", None) or {}
    return environment.get(key) if isinstance(environment, dict) else None


def aggregate(rows, *, min_sample: int = 30, adjustment_points: float = 2.0) -> dict[tuple, EnvironmentMemoryEvidence]:
    buckets: dict[tuple, list] = {}
    for row in rows:
        if getattr(row, "outcome", None) not in RESOLVED:
            continue
        key = (getattr(row, "symbol", None) or "(unknown)", getattr(row, "strategy", None) or "STRATEGY_NONE", getattr(row, "environment_key", None) or "(legacy-unkeyed)", _env(row, "regime") or getattr(row, "regime", None) or "REGIME_UNDEFINED", _env(row, "volatility_state") or "VOL_REGIME_UNDEFINED", _env(row, "news_state") or "NEWS_NONE", _env(row, "session") or getattr(row, "session", None) or "SESSION_DEAD", _env(row, "htf_ob_state"), _env(row, "value_area_zone"), _env(row, "market_phase"), _env(row, "market_structure"))
        buckets.setdefault(key, []).append(row)
    result: dict[tuple, EnvironmentMemoryEvidence] = {}
    for key, group in buckets.items():
        ordered = sorted(group, key=lambda r: getattr(r, "received_at", None) or 0)
        n = len(ordered);wins = sum(1 for r in ordered if r.outcome == "win");losses = sum(1 for r in ordered if r.outcome == "loss");scratches = sum(1 for r in ordered if r.outcome == "scratch")
        r_values = [r.realized_r for r in ordered if r.realized_r is not None];gains = sum(v for v in r_values if v > 0);loss_abs = abs(sum(v for v in r_values if v < 0));cumulative = peak = max_dd = 0.0
        for value in r_values:
            cumulative += value;peak = max(peak, cumulative);max_dd = max(max_dd, peak - cumulative)
        mae = [r.mae_r for r in ordered if r.mae_r is not None];mfe = [r.mfe_r for r in ordered if r.mfe_r is not None];durations = [r.bars_held for r in ordered if r.bars_held is not None];resolved = wins + losses;ci_low, ci_high = wilson_interval(wins, resolved)
        evidence = EnvironmentMemoryEvidence(n,wins,losses,scratches,wins / resolved if resolved else None,ci_low,ci_high,mean(r_values) if r_values else None,gains / loss_abs if loss_abs else (inf if gains > 0 else 0.0),max_dd if r_values else None,mean(mae) if mae else None,mean(mfe) if mfe else None,mean(durations) if durations else None,"UNKNOWN",0.0)
        status = _quality(evidence, min_sample=min_sample);adjustment = adjustment_points if status == "QUALIFIED" else -adjustment_points if status == "DEGRADED" else 0.0
        result[key] = EnvironmentMemoryEvidence(**{**asdict(evidence), "status": status, "adjustment": adjustment})
    return result


def as_report(rows, *, min_sample: int = 30) -> list[dict]:
    matrix = aggregate(rows, min_sample=min_sample);output = []
    for key, evidence in matrix.items():
        record = dict(zip(["symbol", "strategy", "environment_key", "regime", "vol_regime", "news_risk", "session", "htf_ob_state", "va_zone", "market_phase", "structure_state"], key));record.update(asdict(evidence));output.append(record)
    return sorted(output, key=lambda r: (-r["trades"], r["symbol"], r["strategy"], r["regime"]))
