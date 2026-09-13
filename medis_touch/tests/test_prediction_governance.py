from medis_touch.app.prediction_governance import (
    BrokerTruth,
    CalibrationModel,
    EvidenceState,
    LocalState,
    ModelVersions,
    Prediction,
    RegimeSnapshot,
    ResolvedObservation,
    allocate,
    classify_regime,
    reconcile,
    state_fingerprint,
)


def rows(n: int, *, score: float = 0.92, win: bool = True, r: float = 0.5,
         regime: str = "NORMAL", strategy: str = "A"):
    return [ResolvedObservation(score, win, r if win else -1.0, regime, strategy) for _ in range(n)]


def test_calibration_is_empirical_and_never_equals_raw_score_by_definition():
    model = CalibrationModel(min_sample=5)
    model.fit(rows(4) + rows(6, win=False, r=-1.0))
    probability, sample, enough = model.probability(0.92)
    assert probability == 0.4
    assert probability != 0.92
    assert sample == 10
    assert enough
    assert model.expected_return(0.92) == -0.4


def test_insufficient_calibration_is_explicit_not_zero_edge():
    model = CalibrationModel(min_sample=30)
    model.fit(rows(3))
    probability, sample, enough = model.probability(0.92)
    assert probability == 1.0
    assert sample == 3
    assert not enough
    assert model.expected_return(0.92) is None


def test_regime_classification_is_deterministic_from_observables():
    assert classify_regime(volatility="NORMAL", trend="BULL", liquidity="LIQUID", spread="NORMAL", news="CLEAR", shock_indicator=0.1, correlation="DIVERSIFIED") == "NORMAL"
    assert classify_regime(volatility="HIGH", trend="BULL", liquidity="LIQUID", spread="NORMAL", news="CLEAR", shock_indicator=0.4, correlation="DIVERSIFIED") == "TRANSITION"
    assert classify_regime(volatility="HIGH", trend="BULL", liquidity="THIN", spread="DISLOCATED", news="CLEAR", shock_indicator=0.9, correlation="CONCENTRATED") == "SHOCK"


def test_unknown_regime_strategy_gets_baseline_not_zero():
    decision = allocate(observations=rows(2), regime="SHOCK", strategy="A", minimum_sample=30, baseline=0.20)
    assert decision.state is EvidenceState.UNKNOWN
    assert decision.allocation == 0.20
    assert decision.reason == "INSUFFICIENT_EVIDENCE"


def test_underperforming_is_distinct_from_unknown():
    data = rows(30, win=False, r=-1.0)
    decision = allocate(observations=data, regime="NORMAL", strategy="A", minimum_sample=30, baseline=0.20, reliability_threshold=0.5)
    assert decision.state is EvidenceState.UNDERPERFORMING
    assert decision.allocation == 0.20


def test_versioned_prediction_keeps_three_numbers_separate():
    versions = ModelVersions("S42", "C17", "R9", "P12")
    regime = RegimeSnapshot("NORMAL", "NORMAL", "BULL", "LIQUID", "NORMAL", "CLEAR", 0.1, "DIVERSIFIED", "R9")
    p = Prediction(0.92, 0.73, 0.31, regime, "A", versions)
    assert p.model_score == 0.92
    assert p.calibrated_probability == 0.73
    assert p.expected_return == 0.31
    assert p.versions.calibration_version == "C17"


def test_recovery_uses_broker_truth_for_every_boundary_and_is_idempotent():
    broker = BrokerTruth("D1", "O1", "P1", "FILLED", 0.10, 4400.0, "S42/C17/R9/P12")
    local = LocalState("D1", "O1", None, "ORDER_SUBMITTED", 0.10, 4400.0, "S42/C17/R9/P12")
    recovered = reconcile(local, broker)
    assert state_fingerprint(recovered) == state_fingerprint(broker)
    assert reconcile(recovered, broker) == recovered


def test_local_only_state_never_invents_broker_truth():
    local = LocalState("D2", "O2", None, "PERSISTED", 0.10, 4400.0, "S42/C17/R9/P12")
    recovered = reconcile(local, None)
    assert recovered.status == "RECONCILIATION_REQUIRED"
    assert recovered.position_id is None
