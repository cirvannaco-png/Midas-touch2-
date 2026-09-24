"""Clustered MDA for correlated market evidence."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from random import Random
from statistics import mean
from typing import Sequence

from .feature_importance import FeatureRow, Predictor, Scorer


@dataclass(frozen=True)
class FeatureCluster:
    name: str
    features: tuple[str, ...]
    average_abs_correlation: float


@dataclass(frozen=True)
class ClusterImportance:
    cluster: FeatureCluster
    baseline_score: float
    permuted_score_mean: float
    importance: float
    importance_std: float
    repetitions: int


@dataclass(frozen=True)
class ClusteredMDAReport:
    baseline_score: float
    correlation_threshold: float
    repetitions: int
    seed: int
    clusters: tuple[ClusterImportance, ...]


def _corr(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    xd = [x - mx for x in xs]
    yd = [y - my for y in ys]
    denom = sqrt(sum(x * x for x in xd) * sum(y * y for y in yd))
    return 0.0 if denom == 0.0 else sum(x * y for x, y in zip(xd, yd)) / denom


def build_feature_clusters(
    rows: Sequence[FeatureRow],
    feature_names: Sequence[str],
    *,
    correlation_threshold: float = 0.70,
) -> tuple[FeatureCluster, ...]:
    """Use absolute Pearson correlation; derive clusters from training only."""
    if not rows:
        raise ValueError("cluster source dataset must not be empty")
    if not feature_names:
        raise ValueError("at least one feature is required")
    if not 0.0 < correlation_threshold <= 1.0:
        raise ValueError("correlation_threshold must be in (0, 1]")
    values = {name: [float(row[name]) for row in rows] for name in feature_names}
    if not all(isfinite(v) for series in values.values() for v in series):
        raise ValueError("cluster source contains non-finite values")

    parent = {name: name for name in feature_names}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(a: str, b: str) -> None:
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    pair_corr: dict[tuple[str, str], float] = {}
    for i, left in enumerate(feature_names):
        for right in feature_names[i + 1 :]:
            corr = abs(_corr(values[left], values[right]))
            pair_corr[(left, right)] = corr
            if corr >= correlation_threshold:
                union(left, right)

    groups: dict[str, list[str]] = {}
    for name in feature_names:
        groups.setdefault(find(name), []).append(name)

    result = []
    for members in sorted(groups.values(), key=lambda group: group[0]):
        corrs = [
            pair_corr.get((a, b), pair_corr.get((b, a), 1.0))
            for i, a in enumerate(members)
            for b in members[i + 1 :]
        ]
        result.append(
            FeatureCluster(
                name="+".join(members),
                features=tuple(members),
                average_abs_correlation=mean(corrs) if corrs else 1.0,
            )
        )
    return tuple(result)


def clustered_permutation_importance(
    rows: Sequence[FeatureRow],
    targets: Sequence[float],
    *,
    clusters: Sequence[FeatureCluster] | None = None,
    feature_names: Sequence[str] | None = None,
    predictor: Predictor,
    scorer: Scorer,
    correlation_threshold: float = 0.70,
    repetitions: int = 5,
    seed: int = 19,
    higher_is_better: bool = True,
) -> ClusteredMDAReport:
    """Permute correlated evidence groups jointly and measure degradation."""
    if not rows or len(rows) != len(targets):
        raise ValueError("rows and targets must be non-empty and equally sized")
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")
    names = tuple(feature_names or sorted(rows[0]))
    for name in names:
        if any(name not in row for row in rows):
            raise ValueError(f"feature '{name}' is missing")
    source_clusters = tuple(clusters or build_feature_clusters(rows, names, correlation_threshold=correlation_threshold))
    base = [dict(row) for row in rows]
    baseline = float(scorer(targets, [float(predictor(row)) for row in base]))
    if not isfinite(baseline):
        raise ValueError("scorer returned non-finite baseline score")

    rng = Random(seed)
    results = []
    for cluster in source_clusters:
        scores = []
        for _ in range(repetitions):
            indices = list(range(len(base)))
            rng.shuffle(indices)
            permuted = [dict(row) for row in base]
            for feature in cluster.features:
                values = [base[i][feature] for i in indices]
                for row, value in zip(permuted, values):
                    row[feature] = value
            score = float(scorer(targets, [float(predictor(row)) for row in permuted]))
            if not isfinite(score):
                raise ValueError(f"non-finite score for cluster {cluster.name}")
            scores.append(score)
        avg = mean(scores)
        importance = baseline - avg if higher_is_better else avg - baseline
        results.append(
            ClusterImportance(
                cluster=cluster,
                baseline_score=baseline,
                permuted_score_mean=avg,
                importance=importance,
                importance_std=sqrt(mean((x - avg) ** 2 for x in scores)),
                repetitions=repetitions,
            )
        )
    return ClusteredMDAReport(baseline, correlation_threshold, repetitions, seed, tuple(results))
