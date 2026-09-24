"""Held-sample permutation feature-importance (MDA).

Research only. The predictor and metric are injected so this module never
learns or changes live Midas-Touch weights.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from random import Random
from statistics import mean
from typing import Callable, Mapping, Sequence

FeatureRow = Mapping[str, float]
Predictor = Callable[[Mapping[str, float]], float]
Scorer = Callable[[Sequence[float], Sequence[float]], float]


@dataclass(frozen=True)
class FeatureImportance:
    feature: str
    baseline_score: float
    permuted_score_mean: float
    importance: float
    importance_std: float
    repetitions: int


@dataclass(frozen=True)
class FeatureImportanceReport:
    baseline_score: float
    higher_is_better: bool
    repetitions: int
    seed: int
    features: tuple[FeatureImportance, ...]

    def ranked(self) -> tuple[FeatureImportance, ...]:
        return tuple(sorted(self.features, key=lambda item: item.importance, reverse=True))


def permutation_importance(
    rows: Sequence[FeatureRow],
    targets: Sequence[float],
    feature_names: Sequence[str],
    *,
    predictor: Predictor,
    scorer: Scorer,
    repetitions: int = 5,
    seed: int = 17,
    higher_is_better: bool = True,
) -> FeatureImportanceReport:
    """Measure score degradation after independently permuting each feature.

    Correlation structure should be learned from training data; normally call
    this scorer on a held-out sample so importance does not become a tuning
    feedback loop.
    """
    if not rows:
        raise ValueError("feature-importance dataset must not be empty")
    if len(rows) != len(targets):
        raise ValueError("rows and targets must have the same length")
    if not feature_names:
        raise ValueError("at least one feature is required")
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")
    base = [dict(row) for row in rows]
    for feature in feature_names:
        if any(feature not in row for row in base):
            raise ValueError(f"feature '{feature}' is missing from at least one row")

    def predict(sample: Sequence[Mapping[str, float]]) -> list[float]:
        values = [float(predictor(row)) for row in sample]
        if not all(isfinite(value) for value in values):
            raise ValueError("predictor returned a non-finite value")
        return values

    baseline_score = float(scorer(targets, predict(base)))
    if not isfinite(baseline_score):
        raise ValueError("scorer returned a non-finite baseline score")

    rng = Random(seed)
    results: list[FeatureImportance] = []
    for feature in feature_names:
        scores: list[float] = []
        for _ in range(repetitions):
            indices = list(range(len(base)))
            rng.shuffle(indices)
            permuted = [dict(row) for row in base]
            values = [base[index][feature] for index in indices]
            for row, value in zip(permuted, values):
                row[feature] = value
            score = float(scorer(targets, predict(permuted)))
            if not isfinite(score):
                raise ValueError(f"scorer returned non-finite score for '{feature}'")
            scores.append(score)
        avg = mean(scores)
        importance = baseline_score - avg if higher_is_better else avg - baseline_score
        variance = mean((score - avg) ** 2 for score in scores)
        results.append(
            FeatureImportance(
                feature=feature,
                baseline_score=baseline_score,
                permuted_score_mean=avg,
                importance=importance,
                importance_std=sqrt(variance),
                repetitions=repetitions,
            )
        )

    return FeatureImportanceReport(
        baseline_score=baseline_score,
        higher_is_better=higher_is_better,
        repetitions=repetitions,
        seed=seed,
        features=tuple(results),
    )
