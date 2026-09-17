"""Leakage-safe research harness for adaptive environment learning.

The harness deliberately separates training from locked OOS evaluation. It can
be used by the backtest/strategy-tester export path to answer whether adaptive
routing, confluence and SMC architecture add out-of-sample expectancy.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf
from statistics import mean
from typing import Callable, Iterable, Sequence

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


def _filter(rows: Sequence[ResearchObservation], *, htf_ob: bool | None = None,
            value_area: bool | None = None, smc: bool | None = None) -> list[ResearchObservation]:
    return [
        row for row in rows
        if (htf_ob is None or row.htf_ob == htf_ob)
        and (value_area is None or row.value_area == value_area)
        and (smc is None or row.smc == smc)
    ]


def context_ablation(rows: Sequence[ResearchObservation]) -> dict[str, MetricSummary]:
    """Measure the same resolved observations under four context slices.

    This is an attribution diagnostic. A true counterfactual trade-selection
    test must replay the strategy on the same market bars; this function does
    not invent outcomes for trades that were never observed.
    """
    return {
        "base": summarize(rows),
        "base_plus_htf_ob": summarize(_filter(rows, htf_ob=True)),
        "base_plus_value_area": summarize(_filter(rows, value_area=True)),
        "base_plus_both": summarize(_filter(rows, htf_ob=True, value_area=True)),
    }


def architecture_ablation(rows: Sequence[ResearchObservation]) -> dict[str, MetricSummary]:
    """Attribute resolved outcomes to the four requested architecture views."""
    return {
        "midas_full": summarize(rows),
        "midas_without_smc": summarize(_filter(rows, smc=False)),
        "smc_only": summarize(_filter(rows, smc=True)),
        "regime_plus_non_smc": summarize(_filter(rows, smc=False)),
    }


def walk_forward_research(
    rows: Sequence[ResearchObservation],
    *,
    train_size: int,
    test_size: int,
    learner: Callable[[Sequence[ResearchObservation]], object],
    evaluator: Callable[[object, Sequence[ResearchObservation]], MetricSummary],
    step: int | None = None,
) -> tuple[MetricSummary, ...]:
    """Fit only on train data; validation rows are locked from the learner."""
    windows = build_windows(rows, train_size=train_size, test_size=test_size, step=step)
    results: list[MetricSummary] = []
    for window in windows:
        model = learner(rows[window.train_start:window.train_end])
        results.append(evaluator(model, rows[window.test_start:window.test_end]))
    return tuple(results)
