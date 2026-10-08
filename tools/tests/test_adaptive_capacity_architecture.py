from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
GOVERNOR = ROOT / "EA" / "includes" / "Portfolio" / "AdaptiveCapacityGovernor.mqh"
ORDERS = ROOT / "EA" / "includes" / "Execution" / "OrderManager.mqh"
PORTFOLIO = ROOT / "EA" / "includes" / "Portfolio" / "PortfolioManager.mqh"
TRACKER = ROOT / "EA" / "includes" / "Trading" / "OutcomeTrackerLive.mqh"
MONITOR = ROOT / "EA" / "includes" / "Monitoring" / "ProductionMonitor.mqh"


def test_adaptive_capacity_governor_is_wired_into_ea():
    t = EA.read_text()
    assert '#include "includes/Portfolio/AdaptiveCapacityGovernor.mqh"' in t
    assert "CAdaptiveCapacityGovernor g_capacity" in t
    assert "g_capacity.Init(" in t
    assert "g_capacity.Refresh(" in t
    assert "g_capacity.SetContext(" in t


def test_rolling_20_50_and_full_trade_results_drive_capacity():
    t = TRACKER.read_text()
    g = GOVERNOR.read_text()
    assert "ConfigureRollingPerformance" in t
    assert "GetRollingStats" in t
    assert "RecordRollingOutcome(rr,coarseOutcome==\"win\")" in t
    assert "void RecordRollingOutcome(double realizedR,bool win)" in t
    assert "void BuildRollingStats(int window,OutcomeStats &out) const" in t
    assert "m_rollingHead=(m_rollingHead+1)%capacity" in t
    assert "m_shortWindow(20)" in t
    assert "m_longWindow(50)" in t
    assert "shortStats.AverageRMultiple()" in g
    assert "longStats.AverageRMultiple()" in g
    assert "lifetime.AverageRMultiple()" in g


def test_progressive_levels_remain_harder_and_use_pf_wr_avg_r():
    t = GOVERNOR.read_text()
    assert "return 3;" in t
    assert "return 2;" in t or "PromotionMeets(2" in t
    assert "return 1;" in t or "PromotionMeets(1" in t
    assert "m_elitePF" in t
    assert "m_provenPF" in t
    assert "m_strongPF" in t


def test_sample_cooldown_and_confirmation_hysteresis_are_present():
    t = GOVERNOR.read_text()
    assert "m_promotionConfirmations" in t
    assert "m_demotionConfirmations" in t
    assert "PromotionCooldownFor" in t
    assert "m_tradesSinceChange" in t
    assert "RetentionMeets" in t


def test_drawdown_and_context_can_only_remove_extra_capacity():
    g = GOVERNOR.read_text()
    assert "drawdownPercent>=m_capacityBlockDrawdown" in g
    assert "!m_regimeEligible" in g
    assert "!m_executionHealthy" in g
    assert "m_baselineMaxOpen" in g


def test_order_manager_has_dynamic_admission_ceiling_without_forced_closes():
    t = ORDERS.read_text()
    assert "SetMaxOpenTrades" in t
    assert "MaxOpenTrades() const" in t
    assert "Existing trades are never closed solely because capacity contracts." in t


def test_portfolio_position_count_limits_and_correlation_risk_brake_are_separate_from_total_risk():
    t = PORTFOLIO.read_text()
    assert "SetPositionLimits" in t
    assert "SetCorrelationGroupRiskLimit" in t
    assert "m_maxCorrelationGroupRiskPercent" in t
    assert "m_maxPortfolioRiskPercent" in t


def test_execution_health_kill_switch_is_capacity_only():
    t = MONITOR.read_text()
    assert "CapacityExpansionHealthy" in t
    assert "m_recentBrokerRejects" in t
    assert "m_capacityLatencyFault" in t
    assert "m_maxRecentBrokerRejects" in t
    assert "return m_recentBrokerRejects<=m_maxRecentBrokerRejects" in t
    e = EA.read_text()
    assert "InpAdaptiveCapacityMaxRecentBrokerRejects" in e
    assert "InpAdaptiveCapacityMaxFillLatencyMs" in e

def test_baseline_risk_envelope_is_unchanged():
    t = EA.read_text()
    assert "input double InpRiskPercentPerTrade=0.5;" in t
    assert "input double InpMaxPortfolioRiskPercent=3.0;" in t
    assert "input int InpMaxOpenTrades=3;" in t
    assert "input int InpMaxPositionsPerSymbol=3;" in t
    assert "input int InpMaxPositionsPerGroup=3;" in t
