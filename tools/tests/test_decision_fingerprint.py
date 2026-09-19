from tools.decision_fingerprint import canonical_serialize, fingerprint


def decision():
    return {
        "decision_id": 7,
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry": 1.12345678,
        "invalidation": 1.12000001,
        "sl": 1.11900001,
        "tp1": 1.13000001,
        "tp2": 1.13500001,
        "final_tp": 1.14000001,
        "confidence": 72,
        "action": "EXECUTE_AND_SIGNAL",
        "reduce_risk": False,
        "spread_points": 8.0,
        "regime": "REGIME_TRENDING",
        "strategy": "STRATEGY_MOMENTUM_BREAKOUT",
        "session": "SESSION_LONDON",
        "weight_version": "v2.10-baseline",
        "strategy_version": "v2.14",
        "model_version": "m1",
        "calibration_version": "c1",
        "feature_schema_version": "f1",
        "environment_schema_version": "e1",
        "environment_key": "env-A",
    }


def test_canonical_serialization_order_and_hash_stable():
    a = decision()
    b = dict(reversed(list(a.items())))
    assert canonical_serialize(a) == canonical_serialize(b)
    assert fingerprint(a) == fingerprint(b)


def test_one_canonical_field_changes_fingerprint():
    a = decision()
    b = dict(a, strategy="STRATEGY_SMC")
    assert fingerprint(a) != fingerprint(b)
