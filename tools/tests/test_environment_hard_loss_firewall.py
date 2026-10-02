from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_environment_hard_loss_firewall_is_feature_flagged_off_by_default():
    zone = _read("EA/includes/Trading/StrategyTradeZone.mqh")
    ea = _read("EA/MedisTouch_v2.8.mq5")
    memory = _read("EA/includes/Trading/EnvironmentStrategyMemory.mqh")

    assert "void ConfigureEnvironmentHardBlock(bool enabled)" in zone
    assert "m_enableEnvironmentHardBlock=false" in zone
    assert 'EnvironmentHardBlocked(const EnvironmentMemoryEvidence &evidence)' in zone
    assert "if(EnvironmentHardBlocked(smcEvidence))smcEligible=false;" in zone
    assert "if(EnvironmentHardBlocked(challengerEvidence))challengerEligible=false;" in zone

    assert "input bool InpEnableEnvironmentHardBlock=false;" in ea
    assert "g_decision.ConfigureEnvironmentHardBlock(InpEnableEnvironmentHardBlock);" in ea

    assert 'bool IsDegraded(const EnvironmentMemoryEvidence &evidence) const' in memory
    assert 'evidence.status=="DEGRADED"' in memory


def test_hard_loss_firewall_only_acts_on_environment_memory_evidence():
    zone = _read("EA/includes/Trading/StrategyTradeZone.mqh")
    assert "if(challengerEligible&&challengerMemory)" in zone
    assert "if(smcEligible&&smcMemory)" in zone
    assert "challengerAdjusted=challengerScore+challengerEvidence.adjustment" in zone
    assert "smcAdjusted=smcScore+smcEvidence.adjustment" in zone
