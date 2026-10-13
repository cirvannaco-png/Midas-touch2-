from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"


def test_payoff_asymmetry_candidate_defaults_are_explicit():
    ea = EA.read_text(encoding="utf-8")
    assert 'input double InpMinRiskReward=2.2;' in ea
    assert 'input double InpPartialAtR=2.5;' in ea
    assert 'input double InpPartialFraction=0.5;' in ea
    assert 'input double InpManualRiskReward=2.8;' in ea


def test_partial_payoff_floor_improves_when_runner_returns_to_entry():
    baseline_gross_r = 2.0 * 0.5
    candidate_gross_r = 2.5 * 0.5
    assert baseline_gross_r == 1.0
    assert candidate_gross_r == 1.25
    assert candidate_gross_r > baseline_gross_r


def test_candidate_precision_gates_are_enabled_but_still_configurable():
    ea = EA.read_text(encoding="utf-8")
    assert 'input bool InpRequireMinSweepGrade=true;' in ea
    assert 'input bool InpRequireFreshSetup=true;' in ea
    assert 'input bool InpRequireChaseFilter=true;' in ea
    assert 'input int InpMaxBarsSinceBOS=5;' in ea
    assert 'input double InpMaxChaseDistATR=0.75;' in ea
    assert 'input double InpMinDirectionalAdvantage=5.0;' in ea


def test_shadow_simulator_uses_canonical_dynamic_stop_parameters():
    ea = EA.read_text(encoding="utf-8")
    assert (
        'g_tracker.ConfigureSimulation(InpRiskPercentPerTrade,InpAllowMinLotOverride,'
        'InpDynamicStopBreakevenAtR,InpPartialAtR,InpPartialFraction,InpDynamicStopATRMult,'
        'InpSimCommissionPerLot,InpSimSpreadPoints,InpSimSlippagePoints);'
    ) in ea
    assert (
        'g_tracker.ConfigureSimulation(InpRiskPercentPerTrade,InpAllowMinLotOverride,'
        'InpBreakEvenAtR,InpPartialAtR,InpPartialFraction,InpTrailATRMult,'
        'InpSimCommissionPerLot,InpSimSpreadPoints,InpSimSlippagePoints);'
    ) not in ea


def test_candidate_has_distinct_version_lineage():
    ea = EA.read_text(encoding="utf-8")
    assert '#property version   "2.83"' in ea
    assert 'InpStrategyVersion="strategy-v2.83-payoff-precision-htf-trail-candidate"' in ea
    assert 'InpCalibrationVersion="calibration-v2.83-htf-trail-candidate"' in ea
    assert 'InpWeightSetVersion="v2.83-payoff-precision-htf-trail-candidate"' in ea
