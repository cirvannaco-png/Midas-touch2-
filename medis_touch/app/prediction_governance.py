"""Midas prediction governance.

Keeps model score, calibrated probability, and expected return as three
independent quantities. Calibration is learned only from resolved,
non-overlapping observations. Regime allocation is conservative until both
sample sufficiency and statistical reliability are demonstrated.

This module is deliberately deterministic and side-effect free so it can be
used by the backend, offline calibration jobs, and fault-injection tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import sqrt
from statistics import mean
from typing import Iterable


class EvidenceState(str, Enum):
    UNKNOWN = "UNKNOWN"
    UNDERPERFORMING = "UNDERPERFORMING"
    PROVEN = "PROVEN"


@dataclass(frozen=True)
class ModelVersions:
    model_version: str
    calibration_version: str
    regime_version: str
    portfolio_version: str


@dataclass(frozen=True)
class RegimeSnapshot:
    """Persisted observable regime inputs; no subjective labels are inferred."""
    regime: str
    volatility_state: str
    trend_state: str
    liquidity_state: str
    spread_execution_state: str
    news_state: str
    shock_indicator: float
    correlation_exposure_state: str
    regime_version: str


@dataclass(frozen=True)
class ResolvedObservation:
    model_score: float
    won: bool
    outcome_r: float
    regime: str
    strategy: str
    costs_r: float = 0.0


@dataclass(frozen=True)
class Prediction:
    model_score: float
    calibrated_probability: float
    expected_return: float
    regime: RegimeSnapshot
    strategy: str
    versions: ModelVersions

    def __post_init__(self) -> None:
        if not 0.0 <= self.model_score <= 1.0:
            raise ValueError("model_score must be in [0, 1]")
        if not 0.0 <= self.calibrated_probability <= 1.0:
            raise ValueError("calibrated_probability must be in [0, 1]")
        if not all((self.model_score, self.calibrated_probability)):
            # Zero is valid; this guard intentionally does nothing beyond
            # keeping the fields explicit in the contract.
            pass


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    sample_count: int
    wins: int
    probability: float
    lower_ci: float
    upper_ci: float


@dataclass(frozen=True)
class AllocationDecision:
    state: EvidenceState
    allocation: float
    sample_count: int
    expectancy_r: float | None
    lower_ci: float | None
    upper_ci: float | None
    reason: str


def _wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = wins / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return max(0.0, c - m), min(1.0, c + m)


class CalibrationModel:
    """Empirical calibration keyed by model-score bucket.

    Observations must already be resolved and belong to the training sample.
    Callers are expected to enforce temporal separation between training and
    evaluation data; the model never silently mixes the two populations.
    """

    def __init__(self, min_sample: int = 30, version: str = "C1") -> None:
        self.min_sample = max(1, min_sample)
        self.version = version
        self._observations: list[ResolvedObservation] = []

    def fit(self, observations: Iterable[ResolvedObservation]) -> None:
        self._observations = list(observations)
        if any(o.model_score < 0 or o.model_score > 1 for o in self._observations):
            raise ValueError("all model scores must be in [0, 1]")

    def bins(self, width: float = 0.05) -> list[CalibrationBin]:
        if not 0 < width <= 1:
            raise ValueError("width must be in (0, 1]")
        count = int(round(1 / width))
        result: list[CalibrationBin] = []
        for i in range(count):
            lo, hi = i * width, min(1.0, (i + 1) * width)
            rows = [o for o in self._observations if lo <= o.model_score < hi or (hi == 1.0 and o.model_score <= hi)]
            wins = sum(o.won for o in rows)
            n = len(rows)
            p = wins / n if n else 0.0
            low, high = _wilson(wins, n)
            result.append(CalibrationBin(lo, hi, n, wins, p, low, high))
        return result

    def probability(self, model_score: float) -> tuple[float, int, bool]:
        if not 0 <= model_score <= 1:
            raise ValueError("model_score must be in [0, 1]")
        b = next(b for b in self.bins() if b.lower <= model_score < b.upper or (b.upper == 1 and model_score <= b.upper))
        # UNKNOWN is not a probability. Return a neutral diagnostic value
        # plus an explicit sufficiency flag; consumers must not relabel it.
        return b.probability, b.sample_count, b.sample_count >= self.min_sample

    def expected_return(self, model_score: float) -> float | None:
        b = next(b for b in self.bins() if b.lower <= model_score < b.upper or (b.upper == 1 and model_score <= b.upper))
        rows = [o for o in self._observations if b.lower <= o.model_score < b.upper or (b.upper == 1 and o.model_score <= b.upper)]
        if len(rows) < self.min_sample:
            return None
        return mean(o.outcome_r - o.costs_r for o in rows)


def classify_regime(*, volatility: str, trend: str, liquidity: str, spread: str,
                    news: str, shock_indicator: float, correlation: str) -> str:
    """Deterministic NORMAL/TRANSITION/SHOCK classification from observables."""
    if shock_indicator >= 0.8 or news == "BLOCKED" or spread == "DISLOCATED":
        return "SHOCK"
    clean_normal = (
        volatility in {"LOW", "NORMAL"} and trend in {"BULL", "BEAR", "NEUTRAL"}
        and liquidity == "LIQUID" and spread == "NORMAL" and news == "CLEAR"
        and shock_indicator < 0.3 and correlation != "CONCENTRATED"
    )
    return "NORMAL" if clean_normal else "TRANSITION"


def allocate(*, observations: Iterable[ResolvedObservation], regime: str, strategy: str,
             minimum_sample: int, baseline: float, reliability_threshold: float = 0.0,
             max_allocation: float = 1.0) -> AllocationDecision:
    """Single portfolio authority for regime/strategy capital allocation."""
    rows = [o for o in observations if o.regime == regime and o.strategy == strategy]
    n = len(rows)
    if n < minimum_sample:
        return AllocationDecision(EvidenceState.UNKNOWN, baseline, n, None, None, None, "INSUFFICIENT_EVIDENCE")
    wins = sum(o.won for o in rows)
    low, high = _wilson(wins, n)
    expectancy = mean(o.outcome_r - o.costs_r for o in rows)
    if low <= reliability_threshold or expectancy <= 0:
        return AllocationDecision(EvidenceState.UNDERPERFORMING, baseline, n, expectancy, low, high, "STATISTICAL_GATE_FAILED")
    return AllocationDecision(EvidenceState.PROVEN, min(max_allocation, max(baseline, expectancy)), n, expectancy, low, high, "VALIDATED_ALLOCATION")


@dataclass(frozen=True)
class BrokerTruth:
    decision_id: str
    broker_order_id: str | None
    position_id: str | None
    status: str
    volume: float
    stop_loss: float | None
    version_fingerprint: str


@dataclass(frozen=True)
class LocalState:
    decision_id: str
    broker_order_id: str | None
    position_id: str | None
    status: str
    volume: float
    stop_loss: float | None
    version_fingerprint: str


def reconcile(local: LocalState | None, broker: BrokerTruth | None) -> LocalState:
    """Reconstruct state from broker truth, deterministically and idempotently."""
    if broker is None:
        if local is None:
            raise RuntimeError("NO_LOCAL_OR_BROKER_STATE")
        # Local-only records cannot prove a live broker position. Mark them
        # unresolved instead of inventing broker truth.
        return LocalState(local.decision_id, local.broker_order_id, local.position_id,
                          "RECONCILIATION_REQUIRED", local.volume, local.stop_loss,
                          local.version_fingerprint)
    return LocalState(broker.decision_id, broker.broker_order_id, broker.position_id,
                      broker.status, broker.volume, broker.stop_loss, broker.version_fingerprint)


def state_fingerprint(state: BrokerTruth | LocalState) -> tuple:
    return (state.decision_id, state.broker_order_id, state.position_id,
            state.status, round(state.volume, 12), state.stop_loss, state.version_fingerprint)
