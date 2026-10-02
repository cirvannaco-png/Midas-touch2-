from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_hierarchical_decision_contracts_exist():
    config = read("EA/includes/Core/Config.mqh")
    quality = read("EA/includes/Decision/DecisionQuality.mqh")
    strategy = read("EA/includes/Trading/StrategyTradeZone.mqh")
    decision = read("EA/includes/Decision/DecisionEngine.mqh")

    for token in (
        "ENUM_STRUCTURAL_STATE",
        "ENUM_DECISION_STATE",
        "ENUM_RISK_CLASS",
        "ENUM_SETUP_LIFECYCLE",
        "ENUM_FIREWALL_LAYER",
        "ENUM_LIQUIDITY_SCOPE",
        "ENUM_LIQUIDITY_ARCHETYPE",
        "SETUP_FILLED",
        "SETUP_MANAGED",
        "SETUP_CLOSED",
    ):
        assert token in config

    for token in (
        "class CStructuralValidator",
        "class CTradeQualityFirewall",
        "DECISION_REJECT",
        "DECISION_WAIT",
        "DECISION_TRADE",
        "FinalizeWithCalibration",
    ):
        assert token in quality

    assert '#include "../Decision/DecisionQuality.mqh"' in strategy
    assert "g_decision.ConfigureDecisionArchitecture" not in strategy
    assert "setup.decision_state == DECISION_REJECT" in decision
    assert "setup.decision_state == DECISION_WAIT" in decision
    assert "setup.decision_state != DECISION_TRADE" in decision


def test_structural_provenance_and_fvg_lifecycle_are_present():
    inducement = read("EA/includes/SmartMoney/Inducement.mqh")
    scoring = read("EA/includes/Analysis/Scoring.mqh")
    fvg = read("EA/includes/SmartMoney/FVG.mqh")

    for token in (
        "FindSingleSwing",
        "INDUCEMENT_STRUCTURE_EQUAL_POOL",
        "INDUCEMENT_STRUCTURE_SINGLE_SWING",
        "sweepPenetrationATR",
        "sweepRejectionRatio",
        "sweepFollowThrough",
        "displacementATR",
    ):
        assert token in inducement

    for token in (
        "inducement_structure_type",
        "liquidity_pool_price",
        "sweep_penetration_atr",
        "sweep_rejection_ratio",
        "displacement_atr",
        "bos_distance_atr",
        "liquidity_scope",
        "liquidity_archetype",
    ):
        assert token in scoring

    assert "FVG_INVALIDATED" in fvg
    assert "cd.close < zone.bottom" in fvg
    assert "cd.close > zone.top" in fvg
    strategy = read("EA/includes/Trading/StrategyTradeZone.mqh")
    assert "Never compare raw bar indices across those series" in strategy
    assert "PeriodSeconds(m_fvgCtx.candles.Timeframe())" in strategy
    assert "zone.time<=ind.bosTime" in strategy


def test_mae_mfe_timing_and_versioned_calibration_are_present():
    live = read("EA/includes/Trading/OutcomeTrackerLive.mqh")
    backtest = read("EA/includes/Trading/OutcomeTracker.mqh")
    calibration = read("EA/includes/Trading/CalibrationEngine.mqh")
    ea = read("EA/MedisTouch_v2.8.mq5")

    for source in (live, backtest):
        for token in ("maeR", "mfeR", "timeToMAE", "timeToMFE"):
            assert token in source

    assert "m_schemaVersion" in calibration
    assert 'schemaVersion = "v1"' in calibration
    assert "InpDecisionRequireCalibration=false" in ea
    assert "InpEnableEnvironmentHardBlock=false" in ea
    assert "InpRequireCausalFVG=false" in ea
    assert "InpEnableStructuralValidator=true" in ea
    assert "InpEnableCorrelationGuard=false" in ea
    assert "ConfigureCorrelationGuard" in read("EA/includes/Portfolio/PortfolioManager.mqh")
    assert "RiskClassSizingMultiplier" in read("EA/includes/Core/Config.mqh")
    assert "setup.setup_lifecycle=SETUP_FILLED" in live
    assert "setup.setup_lifecycle=SETUP_CLOSED" in live
    assert "decision_state" in read("EA/includes/Signals/SignalPublisher.mqh")
    assert "quality_score" in read("EA/includes/Signals/SignalPublisher.mqh")
