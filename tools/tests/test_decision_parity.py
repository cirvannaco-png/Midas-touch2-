from tools.decision_parity import compare


def _decision():
    return {
        "strategy": "STRATEGY_MOMENTUM_BREAKOUT",
        "regime": "REGIME_TRENDING",
        "environment_key": "env-A",
        "confidence": 72.0,
        "risk_allowed": True,
        "news_allowed": True,
        "portfolio_allowed": True,
    }


def test_matching_decisions_pass():
    result = compare(_decision(), _decision())
    assert result.matched
    assert result.mismatches == ()


def test_strategy_mismatch_fails_closed():
    backend = _decision()
    backend["strategy"] = "STRATEGY_SMC"
    result = compare(_decision(), backend)
    assert not result.matched
    assert "strategy" in result.mismatches


def test_risk_gate_mismatch_fails_closed():
    backend = _decision()
    backend["risk_allowed"] = False
    result = compare(_decision(), backend)
    assert not result.matched
    assert "risk_allowed" in result.mismatches
