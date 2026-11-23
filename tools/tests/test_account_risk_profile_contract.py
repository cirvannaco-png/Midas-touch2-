from pathlib import Path


def test_small_account_is_the_default_profile() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    assert "InpAccountRiskProfile=ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT" in ea
    assert "if(!ResolveSelectedAccountRiskProfile()) return INIT_PARAMETERS_INCORRECT;" in ea


def test_automated_and_manual_orders_use_the_resolved_profile() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    runtime = ea[ea.index("int OnInit()"):]
    assert "g_tracker.ConfigureSimulation(g_activeRiskLimits.riskPercentPerTrade" in runtime
    assert "g_orders.Init(&g_broker,g_activeRiskLimits.maxOpenTrades" in runtime
    assert "g_portfolio.Init(g_activeRiskLimits.maxPortfolioRiskPercent,g_activeRiskLimits.maxPositionsPerSymbol,g_activeRiskLimits.maxPositionsPerGroup" in runtime
    assert "g_riskGuard.Init(_Symbol,g_activeRiskLimits.maxDailyLossPercent,g_activeRiskLimits.maxDrawdownPercent,g_activeRiskLimits.deriskStartPercent,g_activeRiskLimits.deriskFloor,InpEnableProgressiveDailyLossDeRisk)" in runtime
    assert "availableSlots=EffectiveMaxOpenTrades()-g_orders.OpenCount()" in runtime
    assert "CalculateLotSize(_Symbol,g_activeRiskLimits.riskPercentPerTrade*fraction" in runtime
    assert "if(g_orders.OpenCount()>=EffectiveMaxOpenTrades())" in runtime
    assert "CalculateLotSize(_Symbol,g_activeRiskLimits.riskPercentPerTrade,entry,setup.stop_loss" in runtime
    for legacy in (
        "InpRiskPercentPerTrade", "InpMaxOpenTrades", "InpMaxDailyLossPercent",
        "InpMaxDrawdownPercent", "InpDeriskStartPercent", "InpDeriskFloor",
        "InpMaxPortfolioRiskPercent", "InpMaxPositionsPerSymbol", "InpMaxPositionsPerGroup",
    ):
        assert legacy not in runtime


def test_four_profile_resolver_has_explicit_mappings_and_config_gates() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    policy = (root / "EA/includes/Portfolio/AccountRiskProfilePolicy.mqh").read_text(encoding="utf-8")
    assert "InpSmallRiskPercentPerTrade=0.5" in ea
    assert "InpLargeRiskPercentPerTrade=20.0" in ea
    assert "InpLargeMinimumRiskPercentPerTrade=15.0" in ea
    assert "InpPropRiskPercentPerTrade=0.5" in ea
    assert "ResolveConfiguredAccountRiskLimits(InpAccountRiskProfile,legacy,smallAccount,largeAccount,propFirm" in ea
    assert "ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT  = 3" in policy
    assert "ValidateAccountRiskLimits(out,reason)" in policy
    assert 'reason="unknown account risk profile"' in policy


def test_startup_ledger_reconciliation_uses_selected_profile_risk() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    start = ea.rindex("bool ReconcileBrokerStateSnapshot()")
    end = ea.index("bool SyncHistoricalClosedPositions()", start)
    reconciliation = ea[start:end]
    assert "g_activeRiskLimits.riskPercentPerTrade" in reconciliation
    assert "InpRiskPercentPerTrade" not in reconciliation


def test_small_account_profile_has_conservative_guardrails() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    policy = (root / "EA/includes/Portfolio/AccountRiskProfilePolicy.mqh").read_text(encoding="utf-8")
    assert "InpSmallRiskPercentPerTrade=0.5" in ea
    assert "InpSmallMaxOpenTrades=1" in ea
    assert "InpSmallMaxDailyLossPercent=1.5" in ea
    assert "InpSmallMaxDrawdownPercent=5.0" in ea
    assert "InpSmallMaxPortfolioRiskPercent=0.5" in ea
    assert "InpSmallMaxPositionsPerSymbol=1" in ea
    assert "InpSmallMaxPositionsPerGroup=1" in ea
    assert "InpSmallAccountProfileConfigured=true" in ea
    assert "MIDAS_SMALL_ACCOUNT_MAX_RISK_PERCENT_PER_TRADE 0.5" in policy
    assert "small-account max open trades exceeds the one-position safety ceiling" in policy
    assert "AUTOMATED_BLOCKED_ACCOUNT_RISK_ADMISSION" in ea
    assert "MANUAL_BLOCKED_ACCOUNT_RISK_ADMISSION" in ea
    assert "InpLargeMinimumRiskPercentPerTrade" in ea


def test_large_account_profile_is_explicit_and_not_the_default() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    policy = (root / "EA/includes/Portfolio/AccountRiskProfilePolicy.mqh").read_text(encoding="utf-8")
    assert "InpAccountRiskProfile=ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT" in ea
    assert "InpLargeRiskPercentPerTrade=20.0" in ea
    assert "InpLargeMaxDailyLossPercent=25.0" in ea
    assert "InpLargeMaxDrawdownPercent=35.0" in ea
    assert "InpLargeDeriskFloor=0.75" in ea
    assert "InpLargeMaxPortfolioRiskPercent=20.0" in ea
    assert "InpLargeAccountProfileConfigured=true" in ea
    assert "MIDAS_LARGE_ACCOUNT_MIN_RISK_PERCENT_PER_TRADE 15.0" in policy
    assert "large-account base risk is below the configured 15% profile floor" in policy


def test_small_account_risk_minimum_is_not_conflated_with_large_account_risk() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    assert "if(g_activeRiskLimits.profile==ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT)" in ea
    assert "if(g_activeRiskLimits.profile!=ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT)" in ea
    manual_start = ea.index("double proposedRisk=g_risk.RiskAmountForLots(_Symbol,lots,entry,setup.stop_loss);")
    manual_end = ea.index("string portfolioReason;", manual_start)
    manual_entry = ea[manual_start:manual_end]
    assert "if(g_activeRiskLimits.profile==ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT)" in manual_entry
    assert "InpLargeMinimumRiskPercentPerTrade" in manual_entry
    assert "ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT" in ea
    assert "SmallAccountRiskAdmission" not in ea
    assert "InpSmallMinimumRiskPercentPerTrade" not in ea
    assert "InpLargeMinimumRiskPercentPerTrade" in ea
    assert "AccountRiskAdmission(bool reduceRisk,string &reasonOut)" in ea


def test_hard_risk_ceiling_is_shared_by_policy_and_lot_sizing() -> None:
    root = Path(__file__).resolve().parents[2]
    policy = (root / "EA/includes/Portfolio/AccountRiskProfilePolicy.mqh").read_text(encoding="utf-8")
    engine = (root / "EA/includes/Trading/RiskEngine.mqh").read_text(encoding="utf-8")
    assert "#define MIDAS_MAX_RISK_PERCENT_PER_TRADE 20.0" in policy
    assert "limits.riskPercentPerTrade>MIDAS_MAX_RISK_PERCENT_PER_TRADE" in policy
    assert "riskPercent>MIDAS_MAX_RISK_PERCENT_PER_TRADE" in engine


def test_dynamic_trailing_stop_remains_enabled_by_default() -> None:
    root = Path(__file__).resolve().parents[2]
    inputs = (root / "EA/includes/Execution/DynamicStopInputs.mqh").read_text(encoding="utf-8")
    manager = (root / "EA/includes/Execution/PositionManager.mqh").read_text(encoding="utf-8")
    assert "InpEnableDynamicStop = true" in inputs
    assert "if(InpEnableDynamicStop && CanModifyNow(ticket))" in manager


def test_dynamic_trailing_stop_cannot_be_disabled_outside_strategy_tester() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    runtime = ea[ea.index("int OnInit()"):]
    guard = "if(!InpEnableDynamicStop && !MQLInfoInteger(MQL_TESTER))"
    assert guard in runtime
    assert "dynamic trailing stop is mandatory outside the Strategy Tester" in runtime
    assert "return INIT_PARAMETERS_INCORRECT;" in runtime
    assert runtime.index(guard) < runtime.index("g_testerDealExport.Init")
