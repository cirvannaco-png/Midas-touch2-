"""Paired counterfactual replay analysis.

A counterfactual is valid only when variants share the same scenario identity.
Unpaired historical subsets are rejected rather than mislabeled as causal
counterfactuals.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf, isfinite
from statistics import mean, median
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CounterfactualMetrics:
    n: int
    expectancy_r: float
    median_r: float
    win_rate: float
    profit_factor: float
    max_drawdown_r: float


@dataclass(frozen=True)
class CounterfactualReport:
    baseline_variant: str
    alternative_variant: str
    paired_scenarios: int
    baseline: CounterfactualMetrics
    alternative: CounterfactualMetrics
    mean_delta_r: float
    median_delta_r: float
    alternative_beats_baseline_fraction: float


def _metrics(values: Sequence[float]) -> CounterfactualMetrics:
    if not values:
        return CounterfactualMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    gross_profit = sum(v for v in values if v > 0)
    gross_loss = -sum(v for v in values if v < 0)
    cumulative = peak = drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    return CounterfactualMetrics(
        n=len(values),
        expectancy_r=mean(values),
        median_r=median(values),
        win_rate=sum(v > 0 for v in values) / len(values),
        profit_factor=gross_profit / gross_loss if gross_loss else (inf if gross_profit else 0.0),
        max_drawdown_r=drawdown,
    )


def compare_counterfactual_variants(
    rows: Sequence[Mapping[str, object]],
    *,
    baseline_variant: str,
    alternative_variant: str,
    scenario_key: str = "scenario_id",
    variant_key: str = "variant",
    outcome_key: str = "realized_r",
    min_pairs: int = 1,
) -> CounterfactualReport:
    """Compare two explicitly paired replay variants."""
    if baseline_variant == alternative_variant:
        raise ValueError("baseline and alternative variants must differ")
    if min_pairs <= 0:
        raise ValueError("min_pairs must be positive")

    groups: dict[str, dict[str, Mapping[str, object]]] = {}
    for row in rows:
        scenario = row.get(scenario_key)
        variant = row.get(variant_key)
        value = row.get(outcome_key)
        if scenario in (None, "") or variant in (None, "") or value is None:
            raise ValueError("counterfactual rows require scenario, variant, and realized R")
        realized = float(value)
        if not isfinite(realized):
            raise ValueError("counterfactual realized R must be finite")
        bucket = groups.setdefault(str(scenario), {})
        key = str(variant)
        if key in bucket:
            raise ValueError(f"duplicate scenario/variant pair: {scenario}/{variant}")
        bucket[key] = row

    relevant = [
        scenario for scenario, variants in groups.items()
        if baseline_variant in variants or alternative_variant in variants
    ]
    if not relevant:
        raise ValueError("no requested counterfactual variants found")
    incomplete = [
        scenario for scenario in relevant
        if baseline_variant not in groups[scenario] or alternative_variant not in groups[scenario]
    ]
    if incomplete:
        raise ValueError(f"counterfactual pairing incomplete for scenarios: {', '.join(incomplete[:5])}")
    if len(relevant) < min_pairs:
        raise ValueError(f"counterfactual sample size {len(relevant)} is below minimum {min_pairs}")

    baseline_values = [float(groups[s][baseline_variant][outcome_key]) for s in relevant]
    alternative_values = [float(groups[s][alternative_variant][outcome_key]) for s in relevant]
    deltas = [a - b for a, b in zip(alternative_values, baseline_values)]
    return CounterfactualReport(
        baseline_variant=baseline_variant,
        alternative_variant=alternative_variant,
        paired_scenarios=len(relevant),
        baseline=_metrics(baseline_values),
        alternative=_metrics(alternative_values),
        mean_delta_r=mean(deltas),
        median_delta_r=median(deltas),
        alternative_beats_baseline_fraction=sum(d > 0 for d in deltas) / len(deltas),
    )
