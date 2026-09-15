from medis_touch.app.institutional_control import (
    AuditDecision,
    ControlInputs,
    ControlState,
    DecisionLineage,
    GateResult,
    PortfolioBudget,
    PromotionEvidence,
    StressScenarioResult,
    admit_budget,
    can_execute,
    control_state,
    promotion_gate,
    summarize_stress,
)


def _evidence(**overrides):
    values = {
        "code_validation": True,
        "data_validation": True,
        "out_of_sample": True,
        "walk_forward": True,
        "stress_test": True,
        "execution_cost_test": True,
        "calibration_test": True,
        "risk_test": True,
        "paper_trade": True,
        "sample_count": 100,
        "minimum_sample": 30,
    }
    values.update(overrides)
    return PromotionEvidence(**values)


def test_promotion_is_fail_closed_on_missing_sample():
    assert promotion_gate(_evidence(sample_count=29)) is GateResult.HOLD
    assert promotion_gate(_evidence(stress_test=False)) is GateResult.FAIL
    assert promotion_gate(_evidence()) is GateResult.PASS


def test_control_halts_on_integrity_failure():
    inputs = ControlInputs(
        venue_healthy=True,
        reconciliation_ok=False,
        market_data_fresh=True,
        risk_ok=True,
        governance_match=True,
    )
    assert control_state(inputs) is ControlState.HALTED


def test_control_restricts_on_drift_without_integrity_failure():
    inputs = ControlInputs(
        venue_healthy=True,
        reconciliation_ok=True,
        market_data_fresh=True,
        risk_ok=True,
        governance_match=True,
        model_drift=True,
    )
    assert control_state(inputs) is ControlState.RESTRICTED


def test_budget_never_over_admits():
    budget = PortfolioBudget("strategy", limit=0.02, used=0.015)
    assert admit_budget(budget, 0.005).admitted
    assert not admit_budget(budget, 0.0051).admitted
    assert not admit_budget(budget, -0.1).admitted


def test_final_execution_gate_requires_normal_state_positive_edge_and_budget():
    budget = PortfolioBudget("strategy", limit=0.02, used=0.01)
    assert can_execute(state=ControlState.NORMAL, expected_return_r=0.2, risk_fraction=0.005, budget=budget)
    assert not can_execute(state=ControlState.RESTRICTED, expected_return_r=0.2, risk_fraction=0.005, budget=budget)
    assert not can_execute(state=ControlState.NORMAL, expected_return_r=0.0, risk_fraction=0.005, budget=budget)
    assert not can_execute(state=ControlState.NORMAL, expected_return_r=0.2, risk_fraction=0.02, budget=budget)


def test_stress_summary_fails_on_integrity_problem_even_if_pnl_passes():
    summary = summarize_stress([
        StressScenarioResult("normal", True, -0.8, True),
        StressScenarioResult("broker_disconnect", True, -1.2, False),
    ])
    assert not summary.passed
    assert summary.integrity_failures == 1


def test_lineage_fingerprint_is_deterministic():
    lineage = DecisionLineage("D1", "M1", "S1", "R1", "C1", "K1", "E1", "CFG")
    assert lineage.fingerprint() == lineage.fingerprint()
    assert len(lineage.fingerprint()) == 64


def test_audit_decision_preserves_independent_prediction_quantities():
    decision = AuditDecision("D1", "BUY", ControlState.NORMAL, "validated", "abc", 0.81, 0.74, 0.22, 0.005)
    assert decision.model_score != decision.calibrated_probability
    assert decision.expected_return_r == 0.22
