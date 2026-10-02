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
        "STRUCTURE_STAGE_FVG_NONCAUSAL",
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
        "bos_age_bars",
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
    assert "STRUCTURE_STAGE_FVG_NONCAUSAL" in read("EA/includes/Decision/DecisionQuality.mqh")


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
    assert "expected_return_r" in read("EA/includes/Signals/SignalPublisher.mqh")
    backtest = read("EA/includes/Trading/OutcomeTracker.mqh")
    partial = backtest[backtest.index("void COutcomeTracker::ApplyPartial"):backtest.index("bool COutcomeTracker::IntrabarReplayGeneric")]
    assert "SETUP_CLOSED" not in partial
    assert "SETUP_MANAGED" in partial
    assert "void COutcomeTracker::FinalizeExit" in backtest
    assert "p.setup.setup_lifecycle=SETUP_CLOSED" in backtest


def test_evidence_families_are_independent_and_capped():
    t=read("EA/includes/Decision/DecisionQuality.mqh")
    assert "structure=0.45*Clamp01(r.bos_strength)" in t
    assert "0.20*EnvironmentFactor(r)" not in t
    assert "r.structure_family_score=30.0*Clamp01(structure)" in t
    assert "r.liquidity_family_score=25.0*Clamp01(liquidity)" in t
    assert "r.location_family_score=20.0*Clamp01(location)" in t
    assert "r.execution_family_score=15.0*Clamp01(execution)" in t
    assert "r.environment_family_score=10.0*EnvironmentFactor(r)" in t


def test_strategy_absence_is_first_class_reject():
    strategy=read("EA/includes/Trading/StrategyTradeZone.mqh")
    logger=read("EA/includes/Core/SignalLogger.mqh")
    assert "TradeSetup CTradeDecision::BuildRejected" in strategy
    assert '"no strategy satisfied the current market/regime admission conditions"' in strategy
    assert "DecisionState" in logger
    assert "BlockingLayer" in logger
    assert "ExpectedReturnR" in logger


def test_inducement_ignores_forming_bar():
    t=read("EA/includes/SmartMoney/Inducement.mqh")
    assert "for(int i = nearIdx - 1; i >= 1; i--)" in t
    assert "for(int i = sweepBarIdx - 1; i >= 1; i--)" in t
    assert "sweepBarIdx-1>=1" in t
    assert "sweepBarIdx>1" in t


def test_elevated_risk_requires_qualified_environment_memory():
    t=read("EA/includes/Decision/DecisionQuality.mqh")
    assert "environmentQualified" in t
    assert 'setup.reasons.environment_memory_status=="QUALIFIED"' in t
    assert "environmentNotDegraded" in t
