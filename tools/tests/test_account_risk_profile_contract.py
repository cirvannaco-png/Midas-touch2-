from pathlib import Path


def test_profile_selector_preserves_legacy_behavior_by_default() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    assert "InpAccountRiskProfile=ACCOUNT_RISK_PROFILE_LEGACY_INPUTS" in ea
    assert "if(!ResolveSelectedAccountRiskProfile()) return INIT_PARAMETERS_INCORRECT;" in ea


def test_automated_and_manual_orders_use_the_resolved_profile() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    runtime = ea[ea.index("int OnInit()"):]
    assert "g_tracker.ConfigureSimulation(g_activeRiskLimits.riskPercentPerTrade" in runtime
    assert "g_orders.Init(&g_broker,g_activeRiskLimits.maxOpenTrades" in runtime
    assert "g_portfolio.Init(g_activeRiskLimits.maxPortfolioRiskPercent,g_activeRiskLimits.maxPositionsPerSymbol,g_activeRiskLimits.maxPositionsPerGroup" in runtime
    assert "g_riskGuard.Init(_Symbol,g_activeRiskLimits.maxDailyLossPercent,g_activeRiskLimits.maxDrawdownPercent,g_activeRiskLimits.deriskStartPercent,g_activeRiskLimits.deriskFloor)" in runtime
    assert "availableSlots=g_activeRiskLimits.maxOpenTrades-g_orders.OpenCount()" in runtime
    assert "CalculateLotSize(_Symbol,g_activeRiskLimits.riskPercentPerTrade*fraction" in runtime
    assert "if(g_orders.OpenCount()>=g_activeRiskLimits.maxOpenTrades)" in runtime
    assert "CalculateLotSize(_Symbol,g_activeRiskLimits.riskPercentPerTrade,entry,setup.stop_loss" in runtime
    # Raw legacy inputs must not bypass resolution after OnInit begins. They remain
    # available only as backward-compatible inputs consumed by the resolver above it.
    for legacy in (
        "InpRiskPercentPerTrade", "InpMaxOpenTrades", "InpMaxDailyLossPercent",
        "InpMaxDrawdownPercent", "InpDeriskStartPercent", "InpDeriskFloor",
        "InpMaxPortfolioRiskPercent", "InpMaxPositionsPerSymbol", "InpMaxPositionsPerGroup",
    ):
        assert legacy not in runtime


def test_profile_resolver_has_explicit_legacy_small_and_prop_firm_mappings() -> None:
    root = Path(__file__).resolve().parents[2]
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    policy = (root / "EA/includes/Portfolio/AccountRiskProfilePolicy.mqh").read_text(encoding="utf-8")
    assert "InpSmallRiskPercentPerTrade" in ea and "InpSmallMaxPortfolioRiskPercent" in ea
    assert "InpPropRiskPercentPerTrade" in ea and "InpPropMaxPortfolioRiskPercent" in ea
    assert "ResolveAccountRiskLimits(InpAccountRiskProfile,legacy,smallAccount,propFirm" in ea
    assert "ValidateAccountRiskLimits(out,reason)" in policy
    assert 'reason="unknown account risk profile"' in policy
