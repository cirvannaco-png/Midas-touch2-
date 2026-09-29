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


def test_smc_validator_preserves_causal_direction_and_no_current_bar_fvg():
    validator = read("EA/includes/SmartMoney/SMCStructuralValidator.mqh")

    assert "z.bar_index <= 0 || z.bar_index > bosBarIndex" in validator
    assert "No causal entry FVG or order block linked to the confirming BOS" in validator
    assert "Structural invalidation level breached" in validator
    assert "SMCStructuralValidation v;" in validator


def test_smc_structure_audit_is_separate_from_legacy_signal_csv():
    logger = read("EA/includes/Core/SignalLogger.mqh")

    assert 'm_smcFilename = "MedisTouch_SMC_Structures_"' in logger
    assert "bool CSignalLogger::LogSMCStructure" in logger
    assert "SignalID" in logger
    assert "FailureReason" in logger
