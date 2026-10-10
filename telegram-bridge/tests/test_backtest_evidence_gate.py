from types import SimpleNamespace

from tools.recalibration_guard import PromotionPolicy
from app.config_promotion_gate import evaluate_challenger


COMPONENTS = {
    "risk_adjusted_return": 0.8,
    "expectancy": 0.8,
    "profit_factor": 0.8,
    "drawdown_control": 0.8,
    "out_of_sample_stability": 0.8,
    "parameter_stability": 0.8,
}


def _evaluation(score, *, validation, decision="VALIDATED"):
    return SimpleNamespace(
        objective_score={"score": score, "components": dict(COMPONENTS)},
        performance_metrics={"locked_oos": {"expectancy_r": 0.4, "profit_factor": 1.5}},
        risk_metrics={"max_drawdown_r": 3.0},
        validation_evidence={
            "training_trades": 100,
            "validation_trades": 50,
            "holdout_trades": 50,
            "purged_walk_forward": True,
            "independent_holdout": True,
            **validation,
        },
        statistical_evidence={},
        regime_conditions={"regime": "TRENDING"},
        provenance={"source": "MT5_STRATEGY_TESTER"},
        decision=decision,
    )


def _policy():
    return PromotionPolicy(
        minimum_score_delta=0.01,
        maximum_oos_degradation=0.35,
        maximum_parameter_degradation=0.10,
    )


def test_challenger_holds_when_new_tester_evidence_failed_quality_gate():
    champion = _evaluation(0.60, validation={})
    challenger = _evaluation(
        0.90,
        validation={
            "oos_degradation": 0.05,
            "parameter_degradation": 0.02,
            "research_pass": True,
            "oos_quality_pass": False,
        },
    )
    decision = evaluate_challenger(champion, challenger, policy=_policy())
    assert decision.action == "HOLD"
    assert any("quality" in reason for reason in decision.reasons)


def test_challenger_holds_when_new_tester_research_artifacts_are_incomplete():
    champion = _evaluation(0.60, validation={})
    challenger = _evaluation(
        0.90,
        validation={
            "oos_degradation": 0.05,
            "parameter_degradation": 0.02,
            "research_pass": False,
            "oos_quality_pass": True,
        },
    )
    decision = evaluate_challenger(champion, challenger, policy=_policy())
    assert decision.action == "HOLD"
    assert any("research evidence" in reason for reason in decision.reasons)


def test_legacy_complete_evidence_remains_compatible():
    champion = _evaluation(0.60, validation={})
    challenger = _evaluation(
        0.90,
        validation={
            "oos_degradation": 0.05,
            "parameter_degradation": 0.02,
        },
    )
    decision = evaluate_challenger(champion, challenger, policy=_policy())
    assert decision.action == "PROMOTE"
