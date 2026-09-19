"""Locked-OOS champion/challenger qualification without tuning the OOS set."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class CandidateEvidence:
    name: str
    sample_size: int
    oos_profit_factor: float | None
    max_drawdown_r: float | None
    win_rate_ci_low: float | None
    win_rate_ci_high: float | None
    cost_robust: bool
    stable_across_regimes: bool
    locked_oos: bool


@dataclass(frozen=True)
class Qualification:
    eligible: bool
    reasons: tuple[str, ...]


def qualify(candidate: CandidateEvidence, *, min_sample: int = 100) -> Qualification:
    reasons: list[str] = []
    if not candidate.locked_oos:
        reasons.append("OOS_NOT_LOCKED")
    if candidate.sample_size < min_sample:
        reasons.append("INSUFFICIENT_SAMPLE")
    if candidate.oos_profit_factor is None or not isfinite(candidate.oos_profit_factor):
        reasons.append("MISSING_OOS_METRIC")
    if candidate.max_drawdown_r is None or not isfinite(candidate.max_drawdown_r):
        reasons.append("MISSING_DRAWDOWN")
    if candidate.win_rate_ci_low is None or candidate.win_rate_ci_high is None:
        reasons.append("MISSING_CONFIDENCE_INTERVAL")
    if not candidate.cost_robust:
        reasons.append("EXECUTION_COST_FRAGILE")
    if not candidate.stable_across_regimes:
        reasons.append("REGIME_INSTABILITY")
    return Qualification(not reasons, tuple(reasons))
