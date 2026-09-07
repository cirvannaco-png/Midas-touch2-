from tools.recalibration_guard import (
    ConfigurationStatus,
    MinimumSamples,
    ObjectiveWeights,
    PromotionPolicy,
    RiskResponse,
    assess_parameter_stability,
    build_purged_walk_forward_plan,
    challenger_passes,
    classify_regime_response,
    ensemble_confidence,
)


def test_objective_is_not_profit_only_and_requires_normalized_components():
    weights = ObjectiveWeights()
    score = weights.score(
        {
            "risk_adjusted_return": 1.0,
            "expectancy": 0.5,
            "profit_factor": 0.5,
            "drawdown_control": 1.0,
            "out_of_sample_stability": 1.0,
            "parameter_stability": 1.0,
        }
    )
    assert 0.0 < score < 1.0


def test_minimum_samples_are_bucket_specific_and_fail_closed():
    policy = MinimumSamples(150, 50, 50)
    assert not policy.satisfied(training=149, validation=50, holdout=50)
    assert policy.satisfied(training=150, validation=50, holdout=50)


def test_purged_walk_forward_keeps_holdout_out_of_folds():
    plan = build_purged_walk_forward_plan(
        500, train_size=200, validation_size=50, step_size=50, purge_size=10, holdout_size=50
    )
    assert plan.holdout_start == 450
    assert all(f.validation_end <= plan.holdout_start for f in plan.folds)
    assert all(f.validation_start - f.train_end == 10 for f in plan.folds)


def test_parameter_plateau_rejects_isolated_spike():
    result = assess_parameter_stability(1.0, [0.99, 0.98, 0.97], max_degradation=0.05, min_neighbors=3)
    assert result.plateau
    result = assess_parameter_stability(1.0, [0.70, 0.72, 0.75], max_degradation=0.05, min_neighbors=3)
    assert not result.plateau


def test_challenger_requires_margin_and_robustness():
    policy = PromotionPolicy(
        minimum_score_delta=0.05,
        maximum_oos_degradation=0.10,
        maximum_parameter_degradation=0.10,
        maximum_p_value=0.05,
    )
    assert challenger_passes(
        champion_score=0.70,
        challenger_score=0.80,
        oos_degradation=0.05,
        parameter_degradation=0.03,
        statistical_p_value=0.02,
        policy=policy,
    )
    assert not challenger_passes(
        champion_score=0.70,
        challenger_score=0.72,
        oos_degradation=0.01,
        parameter_degradation=0.01,
        statistical_p_value=0.01,
        policy=policy,
    )


def test_regime_response_can_reduce_risk_faster_than_recalibration():
    assert classify_regime_response(0.90, normal_min=0.80, reduced_min=0.50, defensive_min=0.30) == RiskResponse.NORMAL
    assert classify_regime_response(0.60, normal_min=0.80, reduced_min=0.50, defensive_min=0.30) == RiskResponse.REDUCED_RISK
    assert classify_regime_response(0.40, normal_min=0.80, reduced_min=0.50, defensive_min=0.30) == RiskResponse.DEFENSIVE
    assert classify_regime_response(0.20, normal_min=0.80, reduced_min=0.50, defensive_min=0.30) == RiskResponse.NO_NEW_TRADES


def test_regime_ensemble_is_weightable_and_bounded():
    confidence = ensemble_confidence(
        {"trend": 0.88, "volatility": 0.82, "structure": 0.91, "momentum": 0.76},
    )
    assert round(confidence, 4) == 0.8425


def test_status_contract_includes_quarantine_and_champion():
    assert ConfigurationStatus.QUARANTINE.value == "quarantine"
    assert ConfigurationStatus.CHAMPION.value == "champion"
