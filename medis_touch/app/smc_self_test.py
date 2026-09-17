"""Leakage-safe SMC self-test, stability, and forward-test freeze gates.

This module does not optimize on OOS data. It evaluates already-replayed candidate
configurations, requires a robust performance plateau rather than a single sharp
optimum, and produces an immutable configuration identity for forward testing.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isfinite
from typing import Mapping, Sequence


@dataclass(frozen=True)
class SMCCandidateResult:
    """One locked replay result for one SMC parameter configuration."""

    parameters: Mapping[str, object]
    oos_windows: int
    expectancy_r: float
    profit_factor: float
    max_drawdown_r: float
    win_rate: float
    contribution_vs_baseline_r: float
    contribution_vs_non_smc_r: float
    oos_degradation: float


@dataclass(frozen=True)
class SMCStabilityReport:
    """Evidence that the selected SMC configuration sits on a robust plateau."""

    passed: bool
    best_index: int | None
    stable_indices: tuple[int, ...]
    neighbor_count: int
    max_oos_degradation: float
    reason: str


@dataclass(frozen=True)
class FrozenSMCConfiguration:
    """Immutable SMC configuration identity used for forward-test promotion."""

    parameters: Mapping[str, object]
    config_hash: str
    source_variant: str
    data_version: str
    stability_report_passed: bool


def canonical_parameters(parameters: Mapping[str, object]) -> str:
    """Return deterministic JSON for a candidate parameter payload."""
    return json.dumps(dict(parameters), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def smc_configuration_hash(parameters: Mapping[str, object]) -> str:
    """Return SHA-256 identity for an exact SMC parameter payload."""
    return hashlib.sha256(canonical_parameters(parameters).encode("utf-8")).hexdigest()


def _valid_candidate(candidate: SMCCandidateResult, *, min_oos_windows: int) -> bool:
    return (
        candidate.oos_windows >= min_oos_windows
        and isfinite(candidate.expectancy_r)
        and isfinite(candidate.profit_factor)
        and isfinite(candidate.max_drawdown_r)
        and isfinite(candidate.win_rate)
        and isfinite(candidate.oos_degradation)
        and candidate.expectancy_r > 0.0
        and candidate.profit_factor >= 1.0
        and 0.0 <= candidate.win_rate <= 1.0
        and 0.0 <= candidate.oos_degradation
    )


def _performance_distance(candidate: SMCCandidateResult, best: SMCCandidateResult) -> float:
    """Relative expectancy distance used to identify a performance plateau."""
    scale = max(abs(best.expectancy_r), 1e-9)
    return abs(candidate.expectancy_r - best.expectancy_r) / scale


def evaluate_smc_stability(
    candidates: Sequence[SMCCandidateResult],
    *,
    min_oos_windows: int = 1,
    performance_tolerance: float = 0.10,
    required_neighbors: int = 1,
    max_allowed_degradation: float = 0.35,
) -> SMCStabilityReport:
    """Evaluate OOS candidates for a robust SMC parameter plateau.

    A candidate is eligible only when it has positive expectancy, PF >= 1 and
    complete OOS metrics. The selected point must have at least
    ``required_neighbors`` other eligible configurations within the requested
    performance tolerance. This deliberately rejects a razor-thin optimum.
    """
    if not candidates:
        return SMCStabilityReport(False, None, (), 0, 0.0, "no SMC candidates")
    if performance_tolerance < 0.0:
        raise ValueError("performance_tolerance must be non-negative")
    if required_neighbors < 0:
        raise ValueError("required_neighbors must be non-negative")
    if min_oos_windows <= 0:
        raise ValueError("min_oos_windows must be positive")

    eligible = [
        (index, candidate)
        for index, candidate in enumerate(candidates)
        if _valid_candidate(candidate, min_oos_windows=min_oos_windows)
        and candidate.oos_degradation <= max_allowed_degradation
    ]
    if not eligible:
        return SMCStabilityReport(False, None, (), 0, 0.0, "no candidate passed OOS quality gates")

    best_index, best = max(eligible, key=lambda item: (item[1].expectancy_r, item[1].profit_factor))
    stable = [
        index
        for index, candidate in eligible
        if _performance_distance(candidate, best) <= performance_tolerance
    ]
    neighbor_count = max(0, len(stable) - 1)
    max_degradation = max(candidate.oos_degradation for _, candidate in eligible)
    passed = neighbor_count >= required_neighbors and best.oos_degradation <= max_allowed_degradation
    reason = (
        "robust SMC parameter plateau identified"
        if passed
        else "SMC optimum is insufficiently stable across nearby configurations"
    )
    return SMCStabilityReport(
        passed=passed,
        best_index=best_index,
        stable_indices=tuple(stable),
        neighbor_count=neighbor_count,
        max_oos_degradation=max_degradation,
        reason=reason,
    )


def freeze_smc_configuration(
    candidate: SMCCandidateResult,
    report: SMCStabilityReport,
    *,
    source_variant: str,
    data_version: str,
) -> FrozenSMCConfiguration:
    """Freeze the exact SMC configuration only after the stability gate passes."""
    if not report.passed:
        raise ValueError("cannot freeze SMC configuration before stability gate passes")
    if report.best_index is None:
        raise ValueError("stability report has no selected candidate")
    return FrozenSMCConfiguration(
        parameters=dict(candidate.parameters),
        config_hash=smc_configuration_hash(candidate.parameters),
        source_variant=source_variant,
        data_version=data_version,
        stability_report_passed=True,
    )


def assert_frozen_configuration(
    frozen: FrozenSMCConfiguration,
    live_parameters: Mapping[str, object],
) -> None:
    """Fail closed when forward-test parameters differ from the frozen identity."""
    live_hash = smc_configuration_hash(live_parameters)
    if live_hash != frozen.config_hash:
        raise ValueError(
            "forward-test SMC configuration does not match frozen configuration "
            f"{frozen.config_hash}"
        )
