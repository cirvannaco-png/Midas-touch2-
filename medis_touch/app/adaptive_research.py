"""Leakage-safe research harness for adaptive environment learning.

The harness separates training from locked OOS evaluation and provides
candidate-level diagnostics plus hooks for true Strategy Tester replays.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf
from statistics import mean
from typing import Callable, Iterable, Sequence

from .smc_self_test import (
    FrozenSMCConfiguration,
    SMCCandidateResult,
    SMCStabilityReport,
    evaluate_smc_stability,
    freeze_smc_configuration,
)
from .walk_forward import build_windows


@dataclass(frozen=True)
class ResearchObservation:
    timestamp: object
    strategy: str
    realized_r: float
    environment: dict[str, object]
    htf_ob: bool
    value_area: bool
    smc: bool
    variant: str = "midas_full"


@dataclass(frozen=True)
class MetricSummary:
    n: int
    win_rate: float
    expectancy_r: float
    average_r: float
    profit_factor: float
    max_drawdown_r: float


def summarize(rows: Iterable[ResearchObservation]) -> MetricSummary:
    values = [row.realized_r for row in rows]
    if not values:
        return MetricSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    wins = sum(value > 0 for value in values)
    gross_profit = sum(value for value in values if value > 0)
    gross_loss = -sum(value for value in values if value < 0)
    cumulative = peak = drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    return MetricSummary(
        n=len(values),
        win_rate=wins / len(values),
        expectancy_r=mean(values),
        average_r=mean(values),
        profit_factor=gross_profit / gross_loss if gross_loss else (inf if gross_profit else 0.0),
        max_drawdown_r=drawdown,
    )


def _filter(
    rows: Sequence[ResearchObservation], *,
    htf_ob: bool | None = None,
    value_area: bool | None = None,
    smc: bool | None = None,
) -> list[ResearchObservation]:
    return [
        row
        for row in rows
        if (htf_ob is None or row.htf_ob == htf_ob)
        and (value_area is None or row.value_area == value_area)
        and (smc is None or row.smc == smc)
    ]


def context_ablation(rows: Sequence[ResearchObservation]) -> dict[str, MetricSummary]:
    """Measure observed outcomes under the four requested context slices.

    These are attribution diagnostics. They do not invent counterfactual
    outcomes. True Base/Base+HTF-OB/Base+VA/Base+both strategy tests must replay
    the EA on identical bars and identical execution costs.
    """
    return {
        "base": summarize(rows),
        "base_plus_htf_ob": summarize(_filter(rows, htf_ob=True)),
        "base_plus_value_area": summarize(_filter(rows, value_area=True)),
        "base_plus_both": summarize(_filter(rows, htf_ob=True, value_area=True)),
    }


def architecture_ablation(rows: Sequence[ResearchObservation]) -> dict[str, MetricSummary]:
    """Compare named Strategy Tester variants when replay exports are tagged.

    If variant-tagged replay rows are present, each result is a genuine variant
    result. Without tags, the fallback is explicitly candidate-level attribution
    and is not presented as a counterfactual backtest.
    """
    requested = (
        "midas_full",
        "midas_without_smc",
        "smc_only",
        "regime_plus_non_smc",
    )
    by_variant = {
        name: [row for row in rows if row.variant == name] for name in requested
    }
    if all(by_variant[name] for name in requested):
        return {name: summarize(by_variant[name]) for name in requested}
    return {
        "midas_full": summarize(rows),
        "midas_without_smc": summarize(_filter(rows, smc=False)),
        "smc_only": summarize(_filter(rows, smc=True)),
        "regime_plus_non_smc": summarize(_filter(rows, smc=False)),
    }


def smc_forward_test_gate(
    candidates: Sequence[SMCCandidateResult],
    *,
    selected_candidate_index: int,
    source_variant: str,
    data_version: str,
    min_oos_windows: int = 1,
    performance_tolerance: float = 0.10,
    required_neighbors: int = 1,
    max_allowed_degradation: float = 0.35,
) -> tuple[SMCStabilityReport, FrozenSMCConfiguration]:
    """Lock an SMC configuration for forward testing only after OOS stability passes."""
    report = evaluate_smc_stability(
        candidates,
        min_oos_windows=min_oos_windows,
        performance_tolerance=performance_tolerance,
        required_neighbors=required_neighbors,
        max_allowed_degradation=max_allowed_degradation,
    )
    if report.best_index != selected_candidate_index:
        raise ValueError("selected SMC candidate is not the OOS stability winner")
    frozen = freeze_smc_configuration(
        candidates[selected_candidate_index],
        report,
        source_variant=source_variant,
        data_version=data_version,
    )
    return report, frozen


def walk_forward_research(
    rows: Sequence[ResearchObservation],
    *,
    train_size: int,
    test_size: int,
    learner: Callable[[Sequence[ResearchObservation]], object],
    evaluator: Callable[[object, Sequence[ResearchObservation]], MetricSummary],
    step: int | None = None,
) -> tuple[MetricSummary, ...]:
    """Fit only on training data; validation rows stay locked from the learner."""
    windows = build_windows(rows, train_size=train_size, test_size=test_size, step=step)
    results: list[MetricSummary] = []
    for window in windows:
        model = learner(rows[window.train_start:window.train_end])
        results.append(evaluator(model, rows[window.test_start:window.test_end]))
    return tuple(results)
