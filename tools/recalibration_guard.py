"""Recalibration guardrails for stable-edge selection.

This module is deliberately policy/data-shape code, not a trading strategy.
It provides deterministic gates that a future optimizer/scheduler must pass
before a candidate configuration can replace a deployed champion.

Key invariants:
- optimize for a validated composite objective, not raw profit alone;
- use purged/embargoed walk-forward splits plus an untouched holdout;
- require instrument/timeframe-specific minimum samples;
- prefer parameter plateaus over isolated optima;
- make configurations immutable and content-addressed;
- require quarantine -> shadow -> challenger -> champion promotion;
- make regime transitions capable of reducing risk faster than learning
  can promote a new configuration.

All thresholds are inputs. No numeric threshold here is a claim about the
correct live values for XAUUSD, FX, or any other instrument.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


OBJECTIVE_COMPONENTS = (
    "risk_adjusted_return",
    "expectancy",
    "profit_factor",
    "drawdown_control",
    "out_of_sample_stability",
    "parameter_stability",
)


@dataclass(frozen=True)
class ObjectiveWeights:
    """Validated weights for the recalibration objective.

    Components must already be normalized to a comparable score by the
    caller. Keeping normalization outside this class prevents this policy
    layer from silently inventing metric transforms.
    """

    risk_adjusted_return: float = 0.30
    expectancy: float = 0.20
    profit_factor: float = 0.15
    drawdown_control: float = 0.15
    out_of_sample_stability: float = 0.10
    parameter_stability: float = 0.10

    def __post_init__(self) -> None:
        values = [getattr(self, name) for name in OBJECTIVE_COMPONENTS]
        if any(value < 0 for value in values):
            raise ValueError("objective weights cannot be negative")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError("objective weights must sum to 1.0")

    def score(self, components: Mapping[str, float]) -> float:
        missing = set(OBJECTIVE_COMPONENTS) - set(components)
        if missing:
            raise ValueError(f"missing objective components: {sorted(missing)}")
        values = [components[name] for name in OBJECTIVE_COMPONENTS]
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("normalized objective components must be in [0, 1]")
        return sum(getattr(self, name) * components[name] for name in OBJECTIVE_COMPONENTS)


@dataclass(frozen=True)
class MinimumSamples:
    """Minimum evidence required for a candidate in one instrument/timeframe bucket."""

    training_trades: int
    validation_trades: int
    holdout_trades: int

    def __post_init__(self) -> None:
        if min(self.training_trades, self.validation_trades, self.holdout_trades) < 1:
            raise ValueError("minimum trade counts must be positive")

    def satisfied(self, *, training: int, validation: int, holdout: int) -> bool:
        return (
            training >= self.training_trades
            and validation >= self.validation_trades
            and holdout >= self.holdout_trades
        )


@dataclass(frozen=True)
class WalkForwardWindow:
    """Index boundaries for one purged walk-forward fold."""

    train_start: int
    train_end: int
    validation_start: int
    validation_end: int


@dataclass(frozen=True)
class PurgedWalkForwardPlan:
    """Deterministic fold plan with a purge/embargo between train and validation."""

    folds: tuple[WalkForwardWindow, ...]
    holdout_start: int
    holdout_end: int


def build_purged_walk_forward_plan(
    sample_count: int,
    *,
    train_size: int,
    validation_size: int,
    step_size: int,
    purge_size: int,
    holdout_size: int,
) -> PurgedWalkForwardPlan:
    """Build chronological folds while keeping the final holdout untouched.

    The caller is responsible for ordering samples chronologically and for
    choosing purge/embargo sizes that cover the strategy's label horizon.
    The function never shuffles data and never exposes holdout rows to folds.
    """
    sizes = (sample_count, train_size, validation_size, step_size, purge_size, holdout_size)
    if any(value < 1 for value in sizes):
        raise ValueError("all walk-forward sizes must be positive")
    holdout_start = sample_count - holdout_size
    if holdout_start <= 0:
        raise ValueError("sample_count must leave room for an independent holdout")

    folds: list[WalkForwardWindow] = []
    train_start = 0
    while True:
        train_end = train_start + train_size
        validation_start = train_end + purge_size
        validation_end = validation_start + validation_size
        if validation_end > holdout_start:
            break
        folds.append(
            WalkForwardWindow(train_start, train_end, validation_start, validation_end)
        )
        train_start += step_size
    if not folds:
        raise ValueError("sample_count cannot form a purged walk-forward fold")
    return PurgedWalkForwardPlan(tuple(folds), holdout_start, sample_count)


@dataclass(frozen=True)
class StabilityResult:
    """Neighborhood robustness result for a candidate parameter vector."""

    center_score: float
    neighbor_scores: tuple[float, ...]
    neighbor_floor: float
    degradation: float
    plateau: bool


def assess_parameter_stability(
    center_score: float,
    neighbor_scores: Sequence[float],
    *,
    max_degradation: float,
    min_neighbors: int,
) -> StabilityResult:
    """Require a parameter plateau rather than an isolated spike.

    ``neighbor_scores`` should be produced by a bounded neighborhood search
    around the candidate. The threshold is policy-configurable and should be
    validated on historical experiments before production use.
    """
    if min_neighbors < 1:
        raise ValueError("min_neighbors must be positive")
    if len(neighbor_scores) < min_neighbors:
        return StabilityResult(center_score, tuple(neighbor_scores), 0.0, 1.0, False)
    if not 0.0 <= max_degradation <= 1.0:
        raise ValueError("max_degradation must be in [0, 1]")
    floor = min(neighbor_scores)
    degradation = max(0.0, center_score - floor)
    return StabilityResult(
        center_score=center_score,
        neighbor_scores=tuple(neighbor_scores),
        neighbor_floor=floor,
        degradation=degradation,
        plateau=degradation <= max_degradation,
    )


class ConfigurationStatus(str, Enum):
    OPTIMIZED = "optimized"
    BACKTESTED = "backtested"
    VALIDATED = "validated"
    QUARANTINE = "quarantine"
    SHADOW = "shadow"
    CHALLENGER = "challenger"
    CHAMPION = "champion"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class ImmutableConfiguration:
    """Content-addressed configuration identity and audit metadata."""

    config_id: str
    strategy: str
    instrument: str
    timeframe: str
    parameters: Mapping[str, object]
    creation_timestamp: str
    training_period: str
    validation_period: str
    holdout_period: str
    optimizer_version: str
    data_version: str
    performance_metrics: Mapping[str, float]
    risk_metrics: Mapping[str, float]
    regime_conditions: Mapping[str, str]
    configuration_hash: str
    status: ConfigurationStatus

    @staticmethod
    def calculate_hash(
        *,
        strategy: str,
        instrument: str,
        timeframe: str,
        parameters: Mapping[str, object],
        optimizer_version: str,
        data_version: str,
        regime_conditions: Mapping[str, str],
    ) -> str:
        payload = {
            "strategy": strategy,
            "instrument": instrument,
            "timeframe": timeframe,
            "parameters": parameters,
            "optimizer_version": optimizer_version,
            "data_version": data_version,
            "regime_conditions": regime_conditions,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PromotionPolicy:
    """Evidence requirements for challenger -> champion promotion."""

    minimum_score_delta: float
    maximum_oos_degradation: float
    maximum_parameter_degradation: float
    maximum_p_value: float | None = None

    def __post_init__(self) -> None:
        if self.minimum_score_delta < 0:
            raise ValueError("minimum_score_delta cannot be negative")
        if not 0.0 <= self.maximum_oos_degradation <= 1.0:
            raise ValueError("maximum_oos_degradation must be in [0, 1]")
        if not 0.0 <= self.maximum_parameter_degradation <= 1.0:
            raise ValueError("maximum_parameter_degradation must be in [0, 1]")
        if self.maximum_p_value is not None and not 0.0 < self.maximum_p_value <= 1.0:
            raise ValueError("maximum_p_value must be in (0, 1]")


def challenger_passes(
    *,
    champion_score: float,
    challenger_score: float,
    oos_degradation: float,
    parameter_degradation: float,
    statistical_p_value: float | None,
    policy: PromotionPolicy,
) -> bool:
    """Decide promotion eligibility without inventing a statistical test.

    The p-value is supplied by a separately validated paired/statistical test.
    If the policy requires it, absence of that evidence fails closed.
    """
    if challenger_score - champion_score < policy.minimum_score_delta:
        return False
    if oos_degradation > policy.maximum_oos_degradation:
        return False
    if parameter_degradation > policy.maximum_parameter_degradation:
        return False
    if policy.maximum_p_value is not None:
        if statistical_p_value is None or statistical_p_value > policy.maximum_p_value:
            return False
    return True


class RiskResponse(str, Enum):
    NORMAL = "normal"
    REDUCED_RISK = "reduced_risk"
    DEFENSIVE = "defensive"
    NO_NEW_TRADES = "no_new_trades"


def classify_regime_response(
    confidence: float,
    *,
    normal_min: float,
    reduced_min: float,
    defensive_min: float,
) -> RiskResponse:
    """Map regime confidence to a fast risk response using configured thresholds."""
    thresholds = (defensive_min, reduced_min, normal_min)
    if any(not 0.0 <= value <= 1.0 for value in thresholds):
        raise ValueError("regime thresholds must be in [0, 1]")
    if not defensive_min <= reduced_min <= normal_min:
        raise ValueError("thresholds must satisfy defensive <= reduced <= normal")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0, 1]")
    if confidence >= normal_min:
        return RiskResponse.NORMAL
    if confidence >= reduced_min:
        return RiskResponse.REDUCED_RISK
    if confidence >= defensive_min:
        return RiskResponse.DEFENSIVE
    return RiskResponse.NO_NEW_TRADES


def ensemble_confidence(scores: Mapping[str, float], *, weights: Mapping[str, float] | None = None) -> float:
    """Combine independent regime measurements into one bounded confidence value."""
    if not scores:
        raise ValueError("at least one regime score is required")
    if any(not 0.0 <= value <= 1.0 for value in scores.values()):
        raise ValueError("regime component scores must be in [0, 1]")
    if weights is None:
        return sum(scores.values()) / len(scores)
    if set(weights) != set(scores):
        raise ValueError("regime weights must cover exactly the supplied scores")
    if any(value < 0 for value in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("regime weights must be non-negative and non-zero in total")
    total = sum(weights.values())
    return sum(scores[name] * weights[name] for name in scores) / total
