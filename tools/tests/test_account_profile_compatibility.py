from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
PROFILE_HEADER = ROOT / "EA" / "includes" / "Core" / "AccountProfile.mqh"
PROFILE_DOC = ROOT / "docs" / "ACCOUNT_PROFILES.md"
RISK_GUARD = ROOT / "EA" / "includes" / "Portfolio" / "RiskGuard.mqh"
RISK_ENGINE = ROOT / "EA" / "includes" / "Trading" / "RiskEngine.mqh"


def test_existing_prop_firm_defaults_remain_compatibility_baseline():
    source = EA.read_text()
    required_defaults = (
        "input double InpRiskPercentPerTrade=0.5;",
        "input int InpMaxOpenTrades=3;",
        "input double InpMaxDailyLossPercent=3.0;",
        "input double InpMaxDrawdownPercent=10.0;",
        "input double InpDeriskStartPercent=5.0;",
        "input double InpDeriskFloor=0.25;",
        "input double InpMaxPortfolioRiskPercent=3.0;",
        "input int InpMaxPositionsPerSymbol=3;",
        "input int InpMaxPositionsPerGroup=3;",
        "input bool InpAllowMinLotOverride=false;",
        "input ENUM_MIDAS_ACCOUNT_PROFILE InpAccountProfile=MIDAS_PROFILE_PROP_FIRM;",
    )
    for default in required_defaults:
        assert default in source, f"Existing compatibility default changed or missing: {default}"


def test_micro_account_research_is_documented_as_unvalidated_and_separate():
    doc = PROFILE_DOC.read_text()
    assert "research only" in doc.lower()
    assert "not proven profitable" in doc.lower()
    assert "not all implemented in this EA profile" in doc
    assert "Do not copy the 8% risk" in doc


def test_prop_and_micro_profiles_resolve_independently():
    source = EA.read_text()
    header = PROFILE_HEADER.read_text()
    assert "if(selectedProfile==MIDAS_PROFILE_PROP_FIRM)" in source
    assert "else if(selectedProfile==MIDAS_PROFILE_MICRO_RESEARCH)" in source
    assert 'g_effectiveProfile.profileName="PROP_FIRM";' in source
    assert 'g_effectiveProfile.profileName="MICRO_RESEARCH";' in source
    assert "g_effectiveProfile.riskPercentPerTrade=InpRiskPercentPerTrade;" in source
    assert "g_effectiveProfile.riskPercentPerTrade=8.0;" in source
    assert "g_effectiveProfile.maxOpenTrades=1;" in source
    assert "g_effectiveProfile.maxPortfolioRiskPercent=8.5;" in source
    assert "g_effectiveProfile.maxDailyLossPercent=18.0;" in source
    assert "g_effectiveProfile.maxDrawdownPercent=35.0;" in source
    assert "enum ENUM_MIDAS_ACCOUNT_PROFILE" in header
    assert "return false;" in header


def test_automated_and_manual_orders_use_effective_profile_limits():
    source = EA.read_text()
    manual_start = source.index("void ManualMarketEntry(bool isBuy)")
    manual_end = source.index("void OnChartEvent(", manual_start)
    manual = source[manual_start:manual_end]
    tick_start = source.index("void OnTick()")
    tick_end = source.index("// Persistent per-symbol/per-magic emergency latch", tick_start)
    automated = source[tick_start:tick_end]

    assert "g_effectiveProfile.riskPercentPerTrade" in manual
    assert "g_effectiveProfile.maxOpenTrades" in manual
    assert "g_effectiveProfile.riskPercentPerTrade*fraction" in automated
    assert "g_effectiveProfile.maxOpenTrades-g_orders.OpenCount()" in automated
    assert "g_effectiveProfile.allowMinLotOverride" in manual
    assert "g_effectiveProfile.allowMinLotOverride" in automated
    assert "g_effectiveProfile.maxPortfolioRiskPercent" in source
    assert "g_effectiveProfile.maxPositionsPerSymbol" in source
    assert "g_effectiveProfile.maxPositionsPerGroup" in source
    assert "g_effectiveProfile.maxDailyLossPercent" in source
    assert "g_effectiveProfile.maxDrawdownPercent" in source
    assert "g_effectiveProfile.deriskStartPercent" in source
    assert "g_effectiveProfile.deriskFloor" in source


def test_micro_profile_cannot_execute_without_second_explicit_acknowledgement():
    source = EA.read_text()
    guard_start = source.index("bool IsProfileExecutionAllowed(string &reasonOut)\n  {")
    guard_end = source.index("int OnInit()", guard_start)
    guard = source[guard_start:guard_end]
    manual_start = source.index("void ManualMarketEntry(bool isBuy)")
    manual_end = source.index("void OnChartEvent(", manual_start)
    tick_start = source.index("void OnTick()")
    tick_end = source.index("// Persistent per-symbol/per-magic emergency latch", tick_start)
    assert "InpConfirmMicroResearchExecution=false;" in source
    assert "g_activeProfile==MIDAS_PROFILE_MICRO_RESEARCH && !InpConfirmMicroResearchExecution" in guard
    assert "ACCOUNT_TRADE_MODE_REAL" in guard
    assert "MQLInfoInteger(MQL_TESTER)" in guard
    assert "IsProfileExecutionAllowed(profileBlockReason)" in source[manual_start:manual_end]
    assert "profileExecutionAllowed" in source[tick_start:tick_end]
    assert "PROFILE_EXECUTION_BLOCKED" in source
    assert "MICRO_RESEARCH" in source[source.index("int OnInit()"):source.index("void OnDeinit")]


def test_profile_identity_is_persistent_and_switch_fails_closed_with_exposure():
    source = EA.read_text()
    lock_start = source.index("bool AcquireAccountProfileLock(string &reasonOut)\n  {")
    lock_end = source.index("bool IsProfileExecutionAllowed(string &reasonOut)\n  {", lock_start)
    lock = source[lock_start:lock_end]
    assert "MedisTouch_AccountProfile_" in source
    assert "GlobalVariableSet(key,-1.0)" in lock
    assert "GlobalVariableSet(key,selected)" in lock
    assert "bool storedNumericValid=MathIsValidNumber(stored);" in lock
    assert "if(storedNumericValid)" in lock
    assert "account profile identity was not initialized before existing exposure" in lock
    assert "GlobalVariablesFlush()" in lock
    assert "if(!InpConfirmAccountProfileChange)" in lock
    source_gate = source[source.index("bool IsProfileExecutionAllowed(string &reasonOut)\n  {"):source.index("int OnInit()")]
    assert "GlobalVariableCheck(lockKey)" in source_gate
    assert "this chart's effective profile differs from the persisted account-wide profile" in source_gate
    assert "AccountHasAnyPositionOrOrder()" in lock
    assert "profile change to %s is pending" in lock
    assert "new entries disabled until the account is flat" in lock
    assert "GlobalVariableDel" not in lock
    assert "ManualReset" not in lock


def test_restart_recovery_and_account_protection_state_are_not_reset_by_profile_change():
    source = EA.read_text()
    guard = RISK_GUARD.read_text()
    assert "g_recovery.Recover()" in source
    for key in ("_PeakEquity", "_HardHalted", "_DayStartEquity", "_DayKey"):
        assert key in guard
    lock_start = source.index("bool AcquireAccountProfileLock(string &reasonOut)\n  {")
    lock_end = source.index("bool IsProfileExecutionAllowed(string &reasonOut)\n  {", lock_start)
    lock = source[lock_start:lock_end]
    assert "persisted daily baseline, peak equity, hard-halt, and emergency-stop variables were not reset" in lock
    assert "GlobalVariableDel" not in lock


def test_profile_and_position_sizing_validation_fail_closed():
    header = PROFILE_HEADER.read_text()
    risk_engine = RISK_ENGINE.read_text()
    assert "MathIsValidNumber(cfg.riskPercentPerTrade)" in header
    assert "MathIsValidNumber(cfg.maxPortfolioRiskPercent)" in header
    assert "MathIsValidNumber(cfg.maxDailyLossPercent)" in header
    assert "MathIsValidNumber(cfg.maxDrawdownPercent)" in header
    assert "cfg.deriskStartPercent>=cfg.maxDrawdownPercent" in header
    assert 'cfg.allowMinLotOverride' in header
    assert "if(lots<minLot)" in risk_engine
    assert "return 0.0;" in risk_engine[risk_engine.index("if(lots<minLot)"):risk_engine.index("return lots;")]
    assert "OrderCalcProfit" in risk_engine


def test_profile_status_is_visible_in_control_panel_and_config_is_logged():
    source = EA.read_text()
    assert "MedisTouch PROFILE:" in source
    assert "configSignature" in source
    assert 'StringFormat("%s | %s",g_effectiveProfile.profileName,ControlPanelSessionStatus())' in source


def test_production_defaults_are_not_replaced_by_micro_research_defaults():
    source = EA.read_text()
    # The research-only 8/18/35 values are assigned only to the resolved profile.
    assert "input double InpRiskPercentPerTrade=8.0;" not in source
    assert "input double InpMaxDailyLossPercent=18.0;" not in source
    assert "input double InpMaxDrawdownPercent=35.0;" not in source
