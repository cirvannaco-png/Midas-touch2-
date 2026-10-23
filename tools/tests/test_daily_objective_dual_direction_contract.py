from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
DAILY = ROOT / "EA" / "includes" / "Trading" / "DailyTradeTarget.mqh"
README = ROOT / "EA" / "README.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_daily_objective_tracks_filled_entry_orders_separately_from_qualified_winners():
    ea = read(EA)
    daily = read(DAILY)
    assert "g_dailyTradeTarget.OnEntry(dealTime,executedOrder>0?executedOrder:trans.deal);" in ea
    assert "void OnEntry(datetime at,ulong orderId)" in daily
    assert "EntryCountToday(){Rollover();return m_entryCount;}" in daily
    assert "CountToday(){Rollover();return m_count;}" in daily
    assert "g_dailyTradeTarget.OnQualifiedClose(dealTime,g_tracker.LastFinalizedR(),positionIdentifier);" in ea
    assert "CountEntryMarkersForDateLocked" in daily
    assert "partial fills of the same order remain one entry" in daily


def test_daily_objective_is_informational_and_does_not_manufacture_entries():
    ea = read(EA)
    daily = read(DAILY)
    assert "g_dailyTradeTarget.LogSearchProgress();TradeSetup buySetup=g_decision.GenerateBuySetup();" in ea
    assert "continuing normal setup search, no entries forced." in daily
    assert "InpMinimumQualifiedTradesPerDay=3;" in ea
    tick_start = ea.index("void OnTick()")
    tick_end = ea.index("TradeSetup buySetup=", tick_start)
    tick = ea[tick_start:tick_end]
    assert tick.index("g_riskGuard.IsHardHalted") < tick.index("g_dailyTradeTarget.LogSearchProgress()")
    assert tick.index("g_newsFilter.IsLocked") < tick.index("g_dailyTradeTarget.LogSearchProgress()")
    assert tick.index("IsConfiguredSessionAllowed()") < tick.index("g_dailyTradeTarget.LogSearchProgress()")


def test_qualified_winner_tracking_is_not_disabled_only_because_account_is_netting():
    ea = read(EA)
    assert "bool qualifiedTradeTrackingSupported=InpTrackOutcomes && InpEnableExecution;" in ea
    assert "qualifiedTradeTrackingSupported=InpTrackOutcomes && InpEnableExecution && ((ENUM_ACCOUNT_MARGIN_MODE)" not in ea


def test_concurrent_opposing_positions_require_explicit_input_and_retail_hedging():
    ea = read(EA)
    readme = read(README)
    assert "input bool InpAllowConcurrentOpposingPositions=false;" in ea
    assert "bool IsRetailHedgingAccount()" in ea
    assert "MT5 netting/exchange accounts cannot retain independent opposing positions on the same symbol" in ea
    assert "if(!InpAllowConcurrentOpposingPositions)" in ea
    assert "CanOpenDirectionWithExposure(decision.setup.type,opposingDirectionReason)" in ea
    assert "CanOpenDirectionWithExposure(manualDirection,opposingDirectionReason)" in ea
    assert "retail-hedging" in readme.lower()
    assert "InpAllowConcurrentOpposingPositions" in ea


def test_both_directions_remain_eligible_and_daily_goal_does_not_override_safety_gates():
    ea = read(EA)
    assert "TradeSetup buySetup=g_decision.GenerateBuySetup();TradeSetup sellSetup=g_decision.GenerateSellSetup();" in ea
    assert "if(g_riskGuard.IsHardHalted(haltReason))return;" in ea
    assert "if(g_riskGuard.IsDailyLossLimitHit(haltReason))return;" in ea
    assert "if(InpUseNewsFilter&&g_newsFilter.IsLocked(newsReason))return;" in ea
    assert "if(!IsConfiguredSessionAllowed())" in ea
    assert "g_portfolio.AllowNewTradeBatch(_Symbol,totalProposedRisk,plan.legCount,block)" in ea
