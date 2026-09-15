"""Deterministic adversarial stress scenarios for execution controls."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .institutional_control import ControlInputs, ControlState, control_state


@dataclass(frozen=True)
class StressCase:
    name: str
    inputs: ControlInputs
    expected_state: ControlState


@dataclass(frozen=True)
class StressCaseResult:
    name: str
    passed: bool
    actual_state: ControlState
    expected_state: ControlState


DEFAULT_CASES = (
    StressCase("broker_disconnect", ControlInputs(False, True, True, True, True), ControlState.HALTED),
    StressCase("reconciliation_unknown", ControlInputs(True, False, True, True, True), ControlState.HALTED),
    StressCase("stale_market_data", ControlInputs(True, True, False, True, True), ControlState.HALTED),
    StressCase("risk_breach", ControlInputs(True, True, True, False, True), ControlState.HALTED),
    StressCase("governance_mismatch", ControlInputs(True, True, True, True, False), ControlState.HALTED),
    StressCase("duplicate_order", ControlInputs(True, True, True, True, True, duplicate_orders=1), ControlState.HALTED),
    StressCase("model_drift", ControlInputs(True, True, True, True, True, model_drift=True), ControlState.RESTRICTED),
    StressCase("execution_degradation", ControlInputs(True, True, True, True, True, execution_degraded=True), ControlState.RESTRICTED),
    StressCase("normal", ControlInputs(True, True, True, True, True), ControlState.NORMAL),
)


def run(cases: tuple[StressCase, ...] = DEFAULT_CASES, evaluator: Callable[[ControlInputs], ControlState] = control_state) -> tuple[StressCaseResult, ...]:
    results = []
    for case in cases:
        actual = evaluator(case.inputs)
        results.append(StressCaseResult(case.name, actual is case.expected_state, actual, case.expected_state))
    return tuple(results)


def all_passed(results: tuple[StressCaseResult, ...]) -> bool:
    return bool(results) and all(result.passed for result in results)
