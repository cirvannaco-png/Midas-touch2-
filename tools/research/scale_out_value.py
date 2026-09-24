"""Replay-based scale-out value analysis.

No scale-out result is synthesized from MFE or a final trade result. Policies
must be explicitly tagged variants from the same Strategy Tester replay.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf, isfinite
from statistics import mean, median
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ScaleOutPolicyMetrics:
    policy: str
    n: int
    expectancy_r: float
    median_r: float
    win_rate: float
    profit_factor: float
    max_drawdown_r: float
    average_mfe_capture: float | None
    average_mae_r: float | None
    average_bars_held: float | None
    average_transaction_cost_r: float | None


@dataclass(frozen=True)
class ScaleOutValueReport:
    source: str
    benchmark_policy: str
    policies: tuple[ScaleOutPolicyMetrics, ...]
    paired_expectancy_delta_r: dict[str, float]
    paired_outperformance_fraction: dict[str, float]


def _metrics(rows: Sequence[Mapping[str, object]], policy: str) -> ScaleOutPolicyMetrics:
    values = [float(row["realized_r"]) for row in rows]
    gross_profit = sum(v for v in values if v > 0)
    gross_loss = -sum(v for v in values if v < 0)
    cumulative = peak = drawdown = 0.0
    captures, maes, durations, costs = [], [], [], []
    for row, value in zip(rows, values):
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
        mfe = row.get("mfe_r")
        if mfe not in (None, "") and float(mfe) > 0:
            captures.append(value / float(mfe))
        if row.get("mae_r") not in (None, ""):
            maes.append(float(row["mae_r"]))
        if row.get("bars_held") not in (None, ""):
            durations.append(float(row["bars_held"]))
        if row.get("transaction_cost_r") not in (None, ""):
            costs.append(float(row["transaction_cost_r"]))
    return ScaleOutPolicyMetrics(
        policy=policy,
        n=len(values),
        expectancy_r=mean(values),
        median_r=median(values),
        win_rate=sum(v > 0 for v in values) / len(values),
        profit_factor=gross_profit / gross_loss if gross_loss else (inf if gross_profit else 0.0),
        max_drawdown_r=drawdown,
        average_mfe_capture=mean(captures) if captures else None,
        average_mae_r=mean(maes) if maes else None,
        average_bars_held=mean(durations) if durations else None,
        average_transaction_cost_r=mean(costs) if costs else None,
    )


def compare_scale_out_policies(
    rows: Sequence[Mapping[str, object]],
    *,
    benchmark_policy: str = "full_exit",
    source: str = "STRATEGY_TESTER_REPLAY",
    trade_key: str = "trade_id",
    policy_key: str = "policy",
    min_trades_per_policy: int = 1,
) -> ScaleOutValueReport:
    """Compare exit policies on exactly paired replay trades."""
    if not rows:
        raise ValueError("scale-out dataset must not be empty")
    if min_trades_per_policy <= 0:
        raise ValueError("min_trades_per_policy must be positive")
    by_policy: dict[str, dict[str, Mapping[str, object]]] = {}
    for row in rows:
        if row.get("source") != source:
            raise ValueError(f"scale-out analysis requires source={source}")
        trade_id, policy, realized_r = row.get(trade_key), row.get(policy_key), row.get("realized_r")
        if trade_id in (None, "") or policy in (None, "") or realized_r is None:
            raise ValueError("scale-out rows require trade_id, policy, and realized_r")
        value = float(realized_r)
        if not isfinite(value):
            raise ValueError("scale-out realized R must be finite")
        bucket = by_policy.setdefault(str(policy), {})
        trade_id = str(trade_id)
        if trade_id in bucket:
            raise ValueError(f"duplicate trade/policy pair: {trade_id}/{policy}")
        bucket[trade_id] = row

    if benchmark_policy not in by_policy:
        raise ValueError(f"benchmark policy '{benchmark_policy}' is missing")
    common_ids = set(by_policy[benchmark_policy])
    for policy, trades in by_policy.items():
        if len(trades) < min_trades_per_policy:
            raise ValueError(f"policy '{policy}' has only {len(trades)} trades")
        if policy != benchmark_policy and set(trades) != common_ids:
            raise ValueError(f"policy '{policy}' is not paired to the benchmark on identical trades")

    metrics = tuple(
        _metrics(list(trades.values()), policy)
        for policy, trades in sorted(by_policy.items())
    )
    benchmark = {trade_id: float(row["realized_r"]) for trade_id, row in by_policy[benchmark_policy].items()}
    deltas, fractions = {}, {}
    for policy, trades in sorted(by_policy.items()):
        if policy == benchmark_policy:
            continue
        paired = [float(trades[i]["realized_r"]) - benchmark[i] for i in common_ids]
        deltas[policy] = mean(paired)
        fractions[policy] = sum(v > 0 for v in paired) / len(paired)

    return ScaleOutValueReport(
        source=source,
        benchmark_policy=benchmark_policy,
        policies=metrics,
        paired_expectancy_delta_r=deltas,
        paired_outperformance_fraction=fractions,
    )
