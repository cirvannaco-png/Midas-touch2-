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

    # This stage is intentionally observational. Until ablation/OOS evidence
    # exists, structural validity must not become a hidden execution gate.
    assert "if(!reasons.smc_structural_valid" not in trade_zone
    assert "if(!out.smc_structural_valid" not in trade_zone
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
