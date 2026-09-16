"""Midas institutional control-plane primitives."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite


class ControlState(str, Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    RESTRICTED = "RESTRICTED"
    HALTED = "HALTED"
    UNKNOWN = "UNKNOWN"


class GateResult(str, Enum):
    PASSED = "PASS"
    FAIL = "FAIL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class DecisionLineage:
    decision_id: str
    model_version: str
    strategy_version: str
    regime_version: str
    calibration_version: str
    risk_version: str
    execution_version: str
    configuration_hash: str

    def fingerprint(self) -> str:
        payload = f"{self.decision_id}|{self.model_version}|{self.strategy_version}|{self.regime_version}|{self.calibration_version}|{self.risk_version}|{self.execution_version}|{self.configuration_hash}"
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PortfolioBudget:
    name: str
    limit: float
    used: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("budget name is required")
        if not all(isfinite(value) and value >= 0 for value in (self.limit, self.used)):
            raise ValueError("budget values must be finite and non-negative")
        if self.used > self.limit:
            raise ValueError("budget used cannot exceed limit")

    def remaining(self) -> float:
        return self.limit - self.used

    def admit(self, requested: float) -> bool:
        return isfinite(requested) and requested >= 0.0 and requested <= self.remaining()


@dataclass(frozen=True)
class PortfolioAdmission:
    admitted: bool
    requested: float
    remaining_before: float
    reason: str


def admit_budget(budget: PortfolioBudget, requested: float) -> PortfolioAdmission:
    remaining = budget.remaining()
    if not isfinite(requested) or requested < 0:
        return PortfolioAdmission(False, requested, remaining, "INVALID_REQUEST")
    if requested > remaining:
        return PortfolioAdmission(False, requested, remaining, "BUDGET_EXCEEDED")
    return PortfolioAdmission(True, requested, remaining, "BUDGET_AVAILABLE")


@dataclass(frozen=True)
class PromotionEvidence:
    code_validation: bool
    data_validation: bool
    out_of_sample: bool
    walk_forward: bool
    stress_test: bool
    execution_cost_test: bool
    calibration_test: bool
    risk_test: bool
    paper_trade: bool
    sample_count: int
    minimum_sample: int


def promotion_gate(evidence: PromotionEvidence) -> GateResult:
    if evidence.sample_count < 0 or evidence.minimum_sample <= 0:
        return GateResult.FAIL
    checks = (evidence.code_validation, evidence.data_validation, evidence.out_of_sample, evidence.walk_forward, evidence.stress_test, evidence.execution_cost_test, evidence.calibration_test, evidence.risk_test, evidence.paper_trade)
    if evidence.sample_count < evidence.minimum_sample:
        return GateResult.HOLD
    return GateResult.PASSED if all(checks) else GateResult.FAIL


@dataclass(frozen=True)
class ControlInputs:
    venue_healthy: bool
    reconciliation_ok: bool
    market_data_fresh: bool
    risk_ok: bool
    governance_match: bool
    model_drift: bool = False
    execution_degraded: bool = False
    drawdown_breach: bool = False
    duplicate_orders: int = 0


def control_state(inputs: ControlInputs) -> ControlState:
    if inputs.duplicate_orders < 0:
        return ControlState.HALTED
    critical = (not inputs.venue_healthy, not inputs.reconciliation_ok, not inputs.market_data_fresh, not inputs.risk_ok, not inputs.governance_match, inputs.drawdown_breach, inputs.duplicate_orders > 0)
    if any(critical):
        return ControlState.HALTED
    if inputs.model_drift or inputs.execution_degraded:
        return ControlState.RESTRICTED
    return ControlState.NORMAL


@dataclass(frozen=True)
class ExecutionThrottle:
    window_seconds: float
    max_orders: int
    max_repeats: int

    def __post_init__(self) -> None:
        if not isfinite(self.window_seconds) or self.window_seconds <= 0:
            raise ValueError("window_seconds must be finite and > 0")
        if self.max_orders <= 0 or self.max_repeats <= 0:
            raise ValueError("throttle limits must be positive")


@dataclass(frozen=True)
class ThrottleDecision:
    allowed: bool
    reason: str


def evaluate_throttle(*, throttle: ExecutionThrottle, orders_in_window: int, repeated_executions: int) -> ThrottleDecision:
    if orders_in_window < 0 or repeated_executions < 0:
        return ThrottleDecision(False, "INVALID_THROTTLE_STATE")
    if orders_in_window >= throttle.max_orders:
        return ThrottleDecision(False, "ORDER_RATE_LIMIT")
    if repeated_executions >= throttle.max_repeats:
        return ThrottleDecision(False, "REPEAT_EXECUTION_LIMIT")
    return ThrottleDecision(True, "THROTTLE_AVAILABLE")


@dataclass(frozen=True)
class StressScenarioResult:
    scenario: str
    passed: bool
    max_loss_r: float
    reconciliation_ok: bool
    duplicate_orders: int = 0
    unknown_positions: int = 0


@dataclass(frozen=True)
class StressSummary:
    passed: bool
    scenarios: int
    failed: int
    worst_loss_r: float
    integrity_failures: int


def summarize_stress(results: Iterable[StressScenarioResult]) -> StressSummary:
    rows = tuple(results)
    failed = sum(not row.passed for row in rows)
    integrity_failures = sum((not row.reconciliation_ok) or row.duplicate_orders > 0 or row.unknown_positions > 0 for row in rows)
    worst_loss = min((row.max_loss_r for row in rows), default=0.0)
    return StressSummary(passed=bool(rows) and failed == 0 and integrity_failures == 0, scenarios=len(rows), failed=failed, worst_loss_r=worst_loss, integrity_failures=integrity_failures)


@dataclass(frozen=True)
class AuditDecision:
    decision_id: str
    action: str
    state: ControlState
    reason: str
    lineage_fingerprint: str
    model_score: float
    calibrated_probability: float
    expected_return_r: float
    risk_fraction: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.model_score <= 1.0:
            raise ValueError("model_score must be in [0, 1]")
        if not 0.0 <= self.calibrated_probability <= 1.0:
            raise ValueError("calibrated_probability must be in [0, 1]")
        if not isfinite(self.expected_return_r):
            raise ValueError("expected_return_r must be finite")
        if not isfinite(self.risk_fraction) or self.risk_fraction < 0.0:
            raise ValueError("risk_fraction must be finite and non-negative")


def can_execute(*, state: ControlState, expected_return_r: float, risk_fraction: float, budget: PortfolioBudget) -> bool:
    if state is not ControlState.NORMAL:
        return False
    if not isfinite(expected_return_r) or not isfinite(risk_fraction):
        return False
    if expected_return_r <= 0.0 or risk_fraction <= 0.0:
        return False
    return budget.admit(risk_fraction)
