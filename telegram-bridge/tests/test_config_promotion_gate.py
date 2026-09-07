from types import SimpleNamespace

from app.config_promotion_gate import evaluate_challenger
from tools.recalibration_guard import PromotionPolicy


POLICY = PromotionPolicy(
    minimum_score_delta=0.05,
    maximum_oos_degradation=0.10,
    maximum_parameter_degradation=0.10,
    maximum_p_value=0.05,
)


def evidence(*, score=0.80, p_value=0.01, oos_degradation=0.02, parameter_degradation=0.02):
    return SimpleNamespace(
        objective_score={
            "score": score,
            "components": {
                "risk_adjusted_return": 0.8,
                "expectancy": 0.8,
                "profit_factor": 0.8,
                "drawdown_control": 0.8,
                "out_of_sample_stability": 0.8,
                "parameter_stability": 0.8,
            },
        },
        performance_metrics={"return": 0.1},
        risk_metrics={"drawdown": 0.05},
        validation_evidence={
            "training_trades": 300,
            "validation_trades": 100,
            "holdout_trades": 100,
            "purged_walk_forward": True,
            "independent_holdout": True,
            "oos_degradation": oos_degradation,
            "parameter_degradation": parameter_degradation,
        },
        statistical_evidence={"p_value": p_value},
        regime_conditions={"regime": "trend"},
        provenance={"data_version": "market-v1", "optimizer_version": "opt-v1"},
    )


def test_missing_holdout_evidence_cannot_promote():
    champion = evidence(score=0.70)
    challenger = evidence(score=0.85)
    challenger.validation_evidence = {"purged_walk_forward": True}
    decision = evaluate_challenger(champion, challenger, policy=POLICY)
    assert decision.action == "HOLD"
    assert any("holdout" in reason for reason in decision.reasons)


def test_insufficient_score_delta_cannot_promote():
    decision = evaluate_challenger(evidence(score=0.80), evidence(score=0.82), policy=POLICY)
    assert decision.action == "HOLD"


def test_oos_degradation_rejects_promotion():
    decision = evaluate_challenger(
        evidence(score=0.70), evidence(score=0.85, oos_degradation=0.11), policy=POLICY
    )
    assert decision.action == "HOLD"


def test_missing_required_statistical_evidence_fails_closed():
    challenger = evidence(score=0.85)
    challenger.statistical_evidence = {}
    decision = evaluate_challenger(evidence(score=0.70), challenger, policy=POLICY)
    assert decision.action == "HOLD"
    assert any("statistical" in reason for reason in decision.reasons)


def test_complete_persisted_evidence_can_promote():
    decision = evaluate_challenger(evidence(score=0.70), evidence(score=0.85), policy=POLICY)
    assert decision.action == "PROMOTE"
