from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ea_uses_regime_first_peer_strategy_router():
    ea = _read("EA/MedisTouch_v2.8.mq5")
    router = _read("EA/includes/Trading/StrategyTradeZone.mqh")

    assert 'includes/Trading/StrategyTradeZone.mqh' in ea
    assert 'includes/Trading/TradeZone.mqh' not in ea

    # Structural ordering guard: independent strategy reads happen before
    # peer selection, and setup construction happens only after selection.
    assert router.index("PopulateStrategyReads") < router.index("SelectPeerStrategy")
    assert router.index("SelectPeerStrategy") < router.index("BuildSMC")
    assert router.index("SelectPeerStrategy") < router.index("BuildNonSMC")

    # Non-SMC routing must not call the SMC confidence engine as its gate.
    non_smc_start = router.index("bool CTradeDecision::BuildNonSMC")
    non_smc_end = router.index("TradeSetup CTradeDecision::Generate")
    non_smc = router[non_smc_start:non_smc_end]
    assert "CalculateConfidence" not in non_smc


def test_ci_remains_explicitly_paused():
    ci = _read(".gitlab-ci.yml")
    assert "workflow:" in ci
    assert "- when: never" in ci
