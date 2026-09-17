from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ea_uses_regime_first_peer_strategy_router():
    ea = _read("EA/MedisTouch_v2.8.mq5")
    router = _read("EA/includes/Trading/StrategyTradeZone.mqh")

    assert 'includes/Trading/StrategyTradeZone.mqh' in ea
    assert 'includes/Trading/TradeZone.mqh' not in ea
    assert 'EnvironmentStrategyMemory.mqh' in router

    assert router.index("PopulateStrategyReads") < router.index("SelectPeerStrategy")
    assert router.index("SelectPeerStrategy") < router.index("BuildSMC")
    assert router.index("SelectPeerStrategy") < router.index("BuildNonSMC")

    non_smc_start = router.index("bool CTradeDecision::BuildNonSMC")
    non_smc_end = router.index("TradeSetup CTradeDecision::Generate")
    non_smc = router[non_smc_start:non_smc_end]
    assert "CalculateConfidence" not in non_smc


def test_adaptive_feedback_loop_is_wired():
    ea = _read("EA/MedisTouch_v2.8.mq5")
    router = _read("EA/includes/Trading/StrategyTradeZone.mqh")
    tracker = _read("EA/includes/Trading/OutcomeTrackerLive.mqh")
    publisher = _read("EA/includes/Signals/SignalPublisher.mqh")
    memory = _read("EA/includes/Trading/EnvironmentStrategyMemory.mqh")

    assert "g_environmentMemory.Init" in ea
    assert "GetPointer(g_environmentMemory)" in ea
    assert "GetEvidence(reasons" in router
    assert "RecordOutcome(p.setup.reasons" in tracker
    assert "coarseOutcome=\"win\"" in tracker
    assert "coarseOutcome=\"loss\"" in tracker
    assert "environment_key" in publisher
    assert "environment" in publisher
    assert "WilsonLower" in memory
    assert "MinimumSample" in memory


def test_ci_remains_explicitly_paused():
    ci = _read(".gitlab-ci.yml")
    assert "workflow:" in ci
    assert "- when: never" in ci
