from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_smc_validator_is_wired_into_production_diagnostics_only():
    validator = read("EA/includes/SmartMoney/SMCStructuralValidator.mqh")
    scoring = read("EA/includes/Analysis/Scoring.mqh")
    trade_zone = read("EA/includes/Trading/StrategyTradeZone.mqh")
    config = read("EA/includes/Core/Config.mqh")

    assert "class CSMCStructuralValidator" in validator
    assert "SMCStructuralValidation Validate" in validator
    assert "CSMCStructuralValidator  m_smcValidator" in scoring
    assert "PopulateStructuralValidation" in scoring
    assert "m_scoring.PopulateStructuralValidation(forBuy,reasons)" in trade_zone

    # Structural validation remains non-binding unless the explicit research
    # switch is enabled. The only execution rejection is guarded by that switch.
    generate_start = trade_zone.index("TradeSetup CTradeDecision::Generate(bool forBuy)")
    generate_end = trade_zone.index("TradeSetup CTradeDecision::GenerateBuySetup", generate_start)
    generate_body = trade_zone[generate_start:generate_end]
    assert "if(m_requireSmcStructuralValidity&&!reasons.smc_structural_valid)" in generate_body
    assert "if(selected==STRATEGY_SMC){m_scoring.PopulateStructuralValidation(forBuy,reasons);if(!reasons.smc_structural_valid)" not in generate_body
    assert "input bool InpRequireSMCStructuralValidity=false;" in read("EA/MedisTouch_v2.8.mq5")
    assert "ENUM_SMC_STRUCTURE_STATE" in config
    assert "smc_failure_reason" in config
    # Structural validation must reuse the exact inducement evidence that
    # EvaluateReasons() already collected; a second Validate() call could create
    # a second representation of the same sweep/BOS event.
    scoring = read("EA/includes/Analysis/Scoring.mqh")
    assert "out.smc_inducement = ind;" in scoring
    assert "InducementResult ind = out.smc_inducement;" in scoring
    assert "InducementResult ind = m_inducement.Validate(forBuy);" in scoring
    validation_start = scoring.index("void CScoringEngine::PopulateStructuralValidation")
    validation_end = scoring.index("void CScoringEngine::PopulateStrategyDiagnostics", validation_start)
    validation_body = scoring[validation_start:validation_end]
    assert "m_inducement.Validate(forBuy)" not in validation_body


def test_smc_validator_preserves_causal_direction_and_no_current_bar_fvg():
    validator = read("EA/includes/SmartMoney/SMCStructuralValidator.mqh")

    assert "z.bar_index <= 0 || z.bar_index > sweepBarIndex || z.bar_index < bosBarIndex" in validator
    assert "No causal entry FVG or order block linked to the confirming BOS" in validator
    assert "Structural invalidation level breached" in validator
    assert "displacementBarIndex" in validator or "displacementBarIndex" in read("EA/includes/SmartMoney/Inducement.mqh")
    assert "SMCStructuralValidation v;" in validator
    assert "PeriodSeconds(m_trendCtx.tf) > PeriodSeconds(m_fvgCtx.tf)" in validator
    # Local/causal order blocks must be sourced from the entry-FVG timeframe;
    # the chart-TF SR context may legitimately be different.
    assert "for(int i = 0; i < m_fvgCtx.orderBlock.Count(); i++)" in validator
    assert "for(int i = 0; i < m_srCtx.orderBlock.Count(); i++)" not in validator


def test_smc_structure_audit_is_separate_from_legacy_signal_csv():
    logger = read("EA/includes/Core/SignalLogger.mqh")

    assert 'm_smcFilename = "MedisTouch_SMC_Structures_"' in logger
    assert "bool CSignalLogger::LogSMCStructure" in logger
    assert "SignalID" in logger
    assert "FailureReason" in logger


def test_smc_structural_gate_is_explicit_default_off_and_applies_only_to_smc():
    ea = read("EA/MedisTouch_v2.8.mq5")
    trade_zone = read("EA/includes/Trading/StrategyTradeZone.mqh")

    assert "input bool InpRequireSMCStructuralValidity=false;" in ea
    assert "ConfigureSMCStructuralGate(InpRequireSMCStructuralValidity)" in ea
    assert "bool                            m_requireSmcStructuralValidity;" in trade_zone
    assert "m_requireSmcStructuralValidity=false" in trade_zone
    assert "void ConfigureSMCStructuralGate(bool requireStructuralValidity);" in trade_zone

    smc_branch = 'if(selected==STRATEGY_SMC){m_scoring.PopulateStructuralValidation(forBuy,reasons);'
    assert smc_branch in trade_zone
    gate = "if(m_requireSmcStructuralValidity&&!reasons.smc_structural_valid){"
    assert gate in trade_zone
    gate_index = trade_zone.index(gate)
    assert gate_index > trade_zone.index("m_scoring.PopulateStructuralValidation(forBuy,reasons)")
    # The rejection preserves audit context instead of returning an empty setup.
    gate_body = trade_zone[gate_index:gate_index+700]
    assert "out.type=forBuy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;" in gate_body
    assert "out.creation_time=TimeCurrent();" in gate_body
    assert "out.reasons=reasons;" in gate_body
    assert 'out.reasons.smc_failure_reason="Execution gate rejected: "+reasons.smc_failure_reason;' in gate_body
    assert "out=BuildSMC" in trade_zone[gate_index:gate_index+900]
    assert "bool FindEntryFVG(ENUM_FVG_DIR dir,FVGZone &out,int requiredBarIndex=-1);" in trade_zone
    assert "requiredBarIndex>0&&z.bar_index!=requiredBarIndex" in trade_zone
    assert "if(!reasons.smc_structural_valid||!reasons.smc_fvg_causal||reasons.smc_entry_fvg_bar_index<=0)return setup;" in trade_zone
    assert "FindEntryFVG(forBuy?FVG_BULL:FVG_BEAR,entryFVG,requiredFvgBarIndex)" in trade_zone


    # The structural rejection must happen before the SMC builder. The normal
    # non-SMC branch may still exist after the SMC branch; that is not a fallback
    # from a rejected SMC setup.
    smc_start = trade_zone.index("if(selected==STRATEGY_SMC)")
    gate_index = trade_zone.index(gate, smc_start)
    smc_build_index = trade_zone.index("out=BuildSMC", gate_index)
    nonsmc_index = trade_zone.index("BuildNonSMC", smc_build_index)
    assert smc_start < gate_index < smc_build_index < nonsmc_index


def test_smc_rejections_are_auditable_and_do_not_disappear():
    ea = read("EA/MedisTouch_v2.8.mq5")
    trade_zone = read("EA/includes/Trading/StrategyTradeZone.mqh")
    logger = read("EA/includes/Core/SignalLogger.mqh")

    # Selected SMC decisions are logged before directional selection so both
    # valid and invalid/blocked structural outcomes enter the audit dataset.
    assert "if(buySetup.reasons.selected_strategy==STRATEGY_SMC)g_logger.LogSMCStructure(buySetup,_Symbol,InpFVGTF);" in ea
    assert "if(sellSetup.reasons.selected_strategy==STRATEGY_SMC)g_logger.LogSMCStructure(sellSetup,_Symbol,InpFVGTF);" in ea

    # The structural CSV must accept inactive SMC records; an inactive record
    # is precisely what a hard gate or setup-construction failure produces.
    assert "if(setup.reasons.selected_strategy != STRATEGY_SMC || setup.creation_time <= 0) return false;" in logger

    # Hard-gate rejection preserves the complete SetupReasons payload and
    # annotates the reason instead of returning an informationless zero setup.
    assert 'out.reasons=reasons;out.reasons.smc_failure_reason="Execution gate rejected: "+reasons.smc_failure_reason;' in trade_zone
    assert "out.creation_time=TimeCurrent();" in trade_zone


def test_smc_quality_execution_policy_is_explicit_and_non_smc_thresholds_are_unchanged():
    ea = read("EA/MedisTouch_v2.8.mq5")
    decision = read("EA/includes/Decision/DecisionEngine.mqh")

    assert "input bool InpEnableSMCQualityExecution=true;" in ea
    assert "input double InpSMCQualityMinConfidence=50.0;" in ea
    assert "InpRequirePremiumDiscount=false;" in ea
    assert "InpRequireVolumeConfirmation=false;" in ea
    assert "InpRequireFibonacciZone=false;" in ea
    assert "InpRequireMinSweepGrade=true;" in ea
    assert "InpMinSweepGrade=3;" in ea
    assert "InpMinConfidenceExecute=68.0;" in ea
    assert "InpMinConfidenceSignal=58.0;" in ea

    assert "bool              m_enableSMCQualityExecution;" in decision
    assert "double            m_smcQualityMinConfidence;" in decision
    assert "setup.reasons.selected_strategy == STRATEGY_SMC" in decision
    assert "setup.reasons.sweep_grade >= SWEEP_GRADE_A" in decision
    assert "setup.reasons.bos_strength >= 0.70" in decision
    assert "setup.reasons.time_decay >= 0.75" in decision
    assert "setup.reasons.fresh_fvg" in decision
    assert "!setup.reasons.value_area_contradiction" in decision
    assert "setup.confidence >= executeThreshold || smcQualityPass" in decision
