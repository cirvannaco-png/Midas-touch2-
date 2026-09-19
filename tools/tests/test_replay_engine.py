from tools.replay_engine import replay
from tools.decision_fingerprint import fingerprint


def test_replay_deterministic():
    original = {"decision_id": 1, "symbol": "EURUSD", "strategy": "SMC"}
    original = dict(original, decision_fingerprint=fingerprint(original))
    result = replay(original, lambda ctx: {k: v for k, v in ctx.items() if k != "decision_fingerprint"})
    assert result.matched
    assert result.event == "REPLAY_DETERMINISTIC"


def test_replay_detects_drift():
    original = {"decision_id": 1, "symbol": "EURUSD", "strategy": "SMC"}
    original = dict(original, decision_fingerprint=fingerprint(original))
    result = replay(original, lambda ctx: dict(ctx, strategy="MOMENTUM"))
    assert not result.matched
    assert result.event == "REPLAY_NON_DETERMINISM"
    assert "strategy" in result.mismatches
