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


def test_sweep_followthrough_thresholds_are_separate_and_default_preserving():
    inducement = read("EA/includes/SmartMoney/Inducement.mqh")
    scoring = read("EA/includes/Analysis/Scoring.mqh")
    ea = read("EA/MedisTouch_v2.8.mq5")

    assert "m_followThroughATRMult" in inducement
    assert "m_followThroughBodyRatio" in inducement
    assert "IsDisplacementBarWithThresholds" in inducement
    assert "m_followThroughATRMult(1.2)" in inducement
    assert "m_followThroughBodyRatio(0.6)" in inducement
    assert "m_followThroughATRMult, m_followThroughBodyRatio" in inducement
    assert "r.sweepFollowThrough=(sweepBarIdx-1>=1 ? IsDisplacementBarWithThresholds" in inducement

    assert "followThroughATRMult = 0.0" in inducement
    assert "followThroughBodyRatio = -1.0" in inducement
    assert "followThroughATRMult = 0.0" in scoring
    assert "followThroughBodyRatio = -1.0" in scoring

    assert "InpSweepFollowThroughATRMult=1.2" in ea
    assert "InpSweepFollowThroughBodyRatio=0.6" in ea
    assert "InpSweepFollowThroughATRMult,InpSweepFollowThroughBodyRatio" in ea

    # The new controls are a behavior-preserving separation of thresholds,
    # not an unconditional relaxation of the production gate.
    assert "followThroughATRMult > 0.0 ? followThroughATRMult : m_impulseATRMult" in inducement
    assert "followThroughBodyRatio >= 0.0" in inducement


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


def test_decision_inputs_are_closed_bar_only():
    scoring = read("EA/includes/Analysis/Scoring.mqh")
    strategy = read("EA/includes/Trading/StrategyTradeZone.mqh")
    assert "return m_priceRef.Total()>1 ? m_priceRef.GetCandle(1).close : 0.0;" in scoring
    assert "m_fvgCtx.candles.GetATR(1)" in scoring
    assert "m_bosCtx.candles.GetATR(1)" in scoring
    assert "m_htfObCtx.candles.GetATR(1)" in scoring
    assert "Classify(1)" in scoring
    assert "m_priceRef.GetCandle(0).close" not in strategy
    assert "m_fvgCtx.candles.GetATR(0)" not in strategy
    assert "m_priceRef.GetATR(0)" not in strategy
    assert "m_priceRef.GetCandle(1).close" in strategy
    assert "m_fvgCtx.candles.GetATR(1)" in strategy


def test_structural_validator_requires_complete_provenance():
    quality = read("EA/includes/Decision/DecisionQuality.mqh")
    assert "!r.inducement_valid" in quality
    assert "r.liquidity_scope==LIQUIDITY_SCOPE_UNKNOWN" in quality
    assert "r.liquidity_archetype==LIQUIDITY_ARCHETYPE_NONE" in quality
    assert "r.sweep_follow_through" in quality
    assert "r.displacement_body_ratio<=0.0" in quality
    assert "r.bos_time<=0" in quality
    assert "r.bos_distance_atr<=0.0" in quality
    assert "r.fvg_distance_atr>2.0" in quality


def test_tested_fvg_remains_a_valid_retest_state():
    quality = read("EA/includes/Decision/DecisionQuality.mqh")
    # FVG_TESTED is accepted by the freshness stage and mapped to
    # RETEST_CONFIRMED; strict structural admission must not relabel that
    # legitimate lifecycle state as degraded.
    assert "bool freshOrTested=(r.fvg_state==FVG_FRESH || r.fvg_state==FVG_TESTED);" in quality
    degraded_start = quality.index("bool degraded=")
    degraded_end = quality.index("if(degraded)", degraded_start)
    assert "FVG_TESTED" not in quality[degraded_start:degraded_end]


def test_strict_smc_structural_validity_gate_is_feature_flagged():
    quality = read("EA/includes/Decision/DecisionQuality.mqh")
    strategy = read("EA/includes/Trading/StrategyTradeZone.mqh")
    ea = read("EA/MedisTouch_v2.8.mq5")
    assert "sv.state==STRUCTURE_INVALID" in quality
    assert "sv.state==STRUCTURE_DEGRADED && requireFullyValidSMC" in quality
    assert "m_requireFullyValidSMC" in strategy
    assert "bool requireFullyValidSMC=false" in strategy
    assert "m_requireFullyValidSMC=requireFullyValidSMC" in strategy
    assert "m_requireCausalFVG,m_requireFullyValidSMC" in strategy
    assert "InpRequireSMCStructuralValidity=false" in ea
    assert "InpMaxExecutionSpreadPoints,InpRequireSMCStructuralValidity" in ea
    # Baseline behavior remains available for comparison because the research
    # gate defaults OFF; strict mode is the candidate to validate on MT5 OOS.
    assert "!requireFullyValidSMC" in quality
    assert "structurally degraded setup below the quality threshold" in quality


def test_multi_trade_is_downstream_from_decision_risk():
    multi = read("EA/includes/Portfolio/MultiTradeEngine.mqh")
    assert "setup.decision_state!=DECISION_TRADE" in multi
    assert "setup.risk_class<RISK_CLASS_STANDARD" in multi
    assert "setup.expected_return_r<=0.0" in multi
    assert 'setup.reasons.environment_memory_status=="DEGRADED"' in multi
    assert "setup.reasons.structural_state==STRUCTURE_DEGRADED" in multi


def test_correlation_guard_fails_closed_on_unknown_data():
    portfolio = read("EA/includes/Portfolio/PortfolioManager.mqh")
    assert "return 2.0; // sentinel: correlation unavailable; enabled guard must fail closed" in portfolio
    assert "MathAbs(corr)>1.0" in portfolio
    assert "correlation guard is enabled and therefore refusing new exposure" in portfolio


def test_outcome_trackers_accept_only_trade_admissions():
    live = read("EA/includes/Trading/OutcomeTrackerLive.mqh")
    backtest = read("EA/includes/Trading/OutcomeTracker.mqh")
    guard = "!setup.active||setup.decision_state!=DECISION_TRADE||setup.setup_lifecycle!=SETUP_ENTRY_ELIGIBLE"
    assert guard in live
    assert "setup.decision_state!=DECISION_TRADE" in backtest
    assert "setup.setup_lifecycle!=SETUP_ENTRY_ELIGIBLE" in backtest


def test_sweep_provenance_and_structural_invalidation_are_anchored():
    config = read("EA/includes/Core/Config.mqh")
    inducement = read("EA/includes/SmartMoney/Inducement.mqh")
    scoring = read("EA/includes/Analysis/Scoring.mqh")
    strategy = read("EA/includes/Trading/StrategyTradeZone.mqh")
    publisher = read("EA/includes/Signals/SignalPublisher.mqh")
    logger = read("EA/includes/Core/SignalLogger.mqh")
    for token in ("double sweepPrice;", "datetime sweepTime;"):
        assert token in config
    assert "r.sweepPrice=forBuy?sweepCandle.low:sweepCandle.high;" in inducement
    assert "r.sweepTime=sweepCandle.time;" in inducement
    assert "out.sweep_price = ind.sweepPrice;" in scoring
    assert "out.sweep_time = ind.sweepTime;" in scoring
    assert "setup.invalidation=forBuy?(setup.reasons.sweep_price-0.05*atr):(setup.reasons.sweep_price+0.05*atr);" in strategy
    assert "\\\"sweep_price\\\":" in publisher
    assert "\\\"sweep_time\\\":" in publisher
    assert '"SweepPrice", "SweepTime"' in logger


def test_research_execution_price_matches_live_order_convention():
    strategy = read("EA/includes/Trading/StrategyTradeZone.mqh")
    backtest = read("EA/includes/Trading/OutcomeTracker.mqh")
    assert "double entry=ResolveExecutionEntry(setup);" in strategy
    assert "p.entryRef = ResolveExecutionEntry(setup);" in backtest
    assert "p.sizingEntryPrice = ResolveExecutionEntry(setup);" in backtest
    assert "BUY -> entry_top, SELL -> entry_bottom." in backtest


def test_tracker_is_admitted_only_after_durable_executable_decision():
    ea = read("EA/MedisTouch_v2.8.mq5")
    save_pos = ea.index("if(!g_store.Save(decision))")
    tracker_pos = ea.index("g_tracker.AddSetup(chosen,decision.decision_id,decision.decision_fingerprint)")
    execute_gate = ea.index("if(decision.action==POLICY_EXECUTE_ONLY||decision.action==POLICY_EXECUTE_AND_SIGNAL)")
    assert save_pos >= 0 and tracker_pos > save_pos
    assert tracker_pos < execute_gate
    assert "(decision.action==POLICY_EXECUTE_ONLY||decision.action==POLICY_EXECUTE_AND_SIGNAL)&&InpTrackOutcomes" in ea


def test_reject_preserves_expired_lifecycle():
    strategy = read("EA/includes/Trading/StrategyTradeZone.mqh")
    assert "(q.decision==DECISION_TRADE?SETUP_ENTRY_ELIGIBLE:SETUP_EXPIRED)" in strategy


def test_backtest_risk_sizing_matches_live_policy():
    backtest = read("EA/includes/Trading/OutcomeTracker.mqh")
    assert "CEnvironmentPolicy m_environmentPolicy;" in backtest
    assert "bool reduceRisk = (setup.risk_class == RISK_CLASS_MINIMAL)" in backtest
    assert "m_environmentPolicy.ReduceRisk(setup)" in backtest
    assert "                                      reduceRisk, m_allowMinLotOverride" in backtest


def test_decision_store_persists_full_state_lineage_append_only():
    store = read("EA/includes/Decision/DecisionStore.mqh")
    assert "string p[40]" in store
    assert "p[25]=IntegerToString((int)rec.setup.decision_state)" in store
    assert "p[26]=IntegerToString((int)rec.setup.reasons.structural_state)" in store
    assert "p[27]=IntegerToString((int)rec.setup.reasons.structural_stage)" in store
    assert "p[28]=IntegerToString((int)rec.setup.reasons.decision_blocking_layer)" in store
    assert "p[29]=IntegerToString((int)rec.setup.risk_class)" in store
    assert "p[31]=DoubleToString(rec.setup.calibrated_probability,4)" in store
    assert "p[34]=DoubleToString(rec.setup.reasons.quality_score,4)" in store
    assert "p[35]=DoubleToString(rec.setup.expected_return_r,6)" in store
    assert "if(n>=39)" in store
    assert "p[39]=DoubleToString(rec.setup.calibration_lower_bound,4)" in store
    assert "if(n>=40) rec.setup.calibration_lower_bound=StringToDouble(f[39]);" in store


def test_all_actionable_strategy_routing_is_closed_bar_and_cross_tf_safe():
    builders = read("EA/includes/Trading/StrategySetupBuilders.mqh")
    momentum = read("EA/includes/Strategies/MomentumBreakout.mqh")
    mean_rev = read("EA/includes/Strategies/MeanReversion.mqh")
    keylevel = read("EA/includes/Strategies/KeyLevelReaction.mqh")
    regime = read("EA/includes/Regime/RegimeDetector.mqh")
    phase = read("EA/includes/SmartMoney/MarketPhase.mqh")
    liquidity = read("EA/includes/SmartMoney/Liquidity.mqh")
    for source in (builders, momentum, mean_rev, keylevel, regime, phase):
        assert "GetCandle(0)" not in source
        assert "GetATR(0)" not in source
        assert "Classify(0)" not in source
    assert "HasNearbyLiquidityEvent(const BOSEvent &bos)" in momentum
    assert "m_liquidity.Timeframe()" in momentum
    assert "Timeframe() const" in liquidity
    assert "MathAbs((double)(ev.time - bos.time))" in momentum


def test_fvg_time_is_completion_time():
    fvg = read("EA/includes/SmartMoney/FVG.mqh")
    assert "zone.time = cd0.time;" in fvg
    assert "zone.time = cd1.time;" not in fvg


def test_sweep_quality_interface_matches_implementation():
    scoring = read("EA/includes/Analysis/Scoring.mqh")
    inducement = read("EA/includes/SmartMoney/Inducement.mqh")
    assert "bool allowSingleSwingStructure = false" in scoring
    assert "m_inducement.ConfigureQualityGates(requireMinSweepGrade, minSweepGrade, requireFreshSetup, maxBarsSinceBOS," in scoring
    assert "allowSingleSwingStructure" in scoring
    assert "ConfigureQualityGates(" in inducement
    assert "ENUM_SWEEP_GRADE minSweepGrade" in inducement
    assert "bool allowSingleSwingStructure" in inducement


def test_indicator_uses_hierarchical_closed_bar_admission():
    indicator = read("EA/MedisTouch_Indicator_v2.8.mq5")
    assert "g_fvgCtx.candles.GetATR(0)" not in indicator
    assert "buySetup.decision_state == DECISION_TRADE" in indicator
    assert "sellSetup.decision_state == DECISION_TRADE" in indicator
    assert "reasons.quality_score" in indicator


def test_value_area_profile_is_closed_bar_only():
    value_area = read("EA/includes/SmartMoney/ValueAreaEngine.mqh")
    assert "GetCandle(0)" not in value_area
    assert "GetATR(0)" not in value_area
    assert "GetCandle(1)" in value_area
    assert "GetATR(1)" in value_area
    assert "TimeCurrent()" not in value_area

def test_key_level_candidates_stay_on_the_correct_side():
    t = read("EA/includes/Strategies/KeyLevelReaction.mqh")
    assert "if(forBuy && z.bottom > price) continue;" in t
    assert "if(!forBuy && z.top < price) continue;" in t
    assert "if(dist < 0) continue;" in t
    assert "if(dist < 0) dist = 0.0;" not in t

def test_structural_validator_fails_closed_on_non_finite_inputs():
    t = read("EA/includes/Decision/DecisionQuality.mqh")
    assert "!MathIsValidNumber(r.liquidity_pool_price)" in t
    assert "!MathIsValidNumber(r.sweep_penetration_atr)" in t
    assert "!MathIsValidNumber(r.displacement_atr)" in t
    assert "!MathIsValidNumber(r.bos_distance_atr)" in t
    assert "!MathIsValidNumber(r.fvg_distance_atr)" in t
    assert "if(!MathIsValidNumber(v)) return 0.0;" in t


def test_target_ladder_recovers_stage_from_remaining_volume():
    t = read("EA/includes/Execution/PositionManager.mqh")
    assert "void CPositionManager::SyncTargetStage" in t
    assert "PositionGetDouble(POSITION_VOLUME)" in t
    assert "m_tp1Done[state]=true" in t
    assert "m_tp2Done[state]=true" in t

def test_target_ladder_is_feature_flagged_and_uses_staged_partials():
    ea = read("EA/MedisTouch_v2.8.mq5")
    pm = read("EA/includes/Execution/PositionManager.mqh")
    assert "InpEnableTargetLadder=false" in ea
    assert "InpTP1PartialFraction=0.50" in ea
    assert "InpTP2PartialFraction=0.25" in ea
    assert "m_tp1Done" in pm
    assert "m_tp2Done" in pm
    assert "CloseTargetSlice" in pm
    assert "dec.setup.tp1" in pm
    assert "dec.setup.tp2" in pm
    assert "if(InpEnableTargetLadder)" in pm
    assert "stateAfterStop==TS_PROTECTED || stateAfterStop==TS_FILLED" in pm


def test_calibration_high_conviction_uses_conservative_bound():
    calibration = read("EA/includes/Trading/CalibrationEngine.mqh")
    quality = read("EA/includes/Decision/DecisionQuality.mqh")
    config = read("EA/includes/Core/Config.mqh")
    ea = read("EA/MedisTouch_v2.8.mq5")
    tracker = read("EA/includes/Trading/OutcomeTracker.mqh")
    live = read("EA/includes/Trading/OutcomeTrackerLive.mqh")
    assert "GetConservativeProbability" in calibration
    assert "const double z = 1.96" in calibration
    assert "calibration_lower_bound" in config
    assert "setup.calibration_lower_bound>=minCalibratedProbability" in quality
    assert "chosen.calibration_lower_bound=g_tracker.GetConservativeProbability" in ea
    assert "GetConservativeProbability(double confidence)" in tracker
    assert "GetConservativeProbability(double confidence)" in live
