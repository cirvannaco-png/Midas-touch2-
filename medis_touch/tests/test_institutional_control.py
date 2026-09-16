from medis_touch.app.institutional_control import (
    ControlInputs,
    ControlState,
    DecisionLineage,
    ExecutionThrottle,
    GateResult,
    PortfolioBudget,
    PromotionEvidence,
    StressScenarioResult,
    admit_budget,
    can_execute,
    control_state,
    evaluate_throttle,
    promotion_gate,
    summarize_stress,
)


def _evidence(**overrides):
    values = {"code_validation": True, "data_validation": True, "out_of_sample": True, "walk_forward": True, "stress_test": True, "execution_cost_test": True, "calibration_test": True, "risk_test": True, "paper_trade": True, "sample_count": 100, "minimum_sample": 30}
    values.update(overrides)
    return PromotionEvidence(**values)


def test_promotion_is_fail_closed_on_missing_sample():
    assert promotion_gate(_evidence(sample_count=29)) is GateResult.HOLD
    assert promotion_gate(_evidence(stress_test=False)) is GateResult.FAIL
    assert promotion_gate(_evidence()) is GateResult.PASSED


def test_control_state_halts_on_integrity_failures():
    assert control_state(ControlInputs(False, True, True, True, True)) is ControlState.HALTED
    assert control_state(ControlInputs(True, True, True, True, True, model_drift=True)) is ControlState.RESTRICTED
    assert control_state(ControlInputs(True, True, True, True, True)) is ControlState.NORMAL


def test_budget_admission_is_explicit():
    budget = PortfolioBudget("strategy", 10, 6)
    assert admit_budget(budget, 4).admitted
    assert not admit_budget(budget, 4.1).admitted


def test_execution_gate_requires_positive_expected_return_and_risk():
    budget = PortfolioBudget("risk", 1)
    assert can_execute(state=ControlState.NORMAL, expected_return_r=0.2, risk_fraction=0.1, budget=budget)
    assert not can_execute(state=ControlState.RESTRICTED, expected_return_r=0.2, risk_fraction=0.1, budget=budget)


def test_lineage_is_deterministic():
    lineage = DecisionLineage("d", "m", "s", "r", "c", "risk", "e", "hash")
    assert lineage.fingerprint() == lineage.fingerprint()
    assert len(lineage.fingerprint()) == 64


def test_throttle_blocks_rate_and_repetition():
    throttle = ExecutionThrottle(60, 10, 3)
    assert evaluate_throttle(throttle=throttle, orders_in_window=9, repeated_executions=2).allowed
    assert not evaluate_throttle(throttle=throttle, orders_in_window=10, repeated_executions=0).allowed
    assert not evaluate_throttle(throttle=throttle, orders_in_window=0, repeated_executions=3).allowed


def test_stress_summary_fails_on_integrity_even_when_scenario_passes():
    summary = summarize_stress((StressScenarioResult("x", True, -1, True, duplicate_orders=1),))
    assert not summary.passed
    assert summary.integrity_failures == 1
