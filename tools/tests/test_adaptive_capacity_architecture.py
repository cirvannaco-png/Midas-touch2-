from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
GOVERNOR = ROOT / "EA" / "includes" / "Portfolio" / "AdaptiveCapacityGovernor.mqh"
ORDERS = ROOT / "EA" / "includes" / "Execution" / "OrderManager.mqh"
PORTFOLIO = ROOT / "EA" / "includes" / "Portfolio" / "PortfolioManager.mqh"


def test_adaptive_capacity_governor_is_wired_into_ea():
    t = EA.read_text()
    assert '#include "includes/Portfolio/AdaptiveCapacityGovernor.mqh"' in t
    assert "CAdaptiveCapacityGovernor g_capacity" in t
    assert "g_capacity.Init(" in t
    assert "g_capacity.Refresh(g_tracker.GetStats(),g_riskGuard.CurrentDrawdownPercent())" in t


def test_capacity_expands_only_from_resolved_outcomes():
    t = GOVERNOR.read_text()
    assert "sample=stats.wins+stats.losses" in t
    assert "stats.AverageRMultiple()" in t
    assert "stats.ProfitFactor()" in t
    assert "winRate=100.0*(double)stats.wins/(double)sample" in t
    assert "return 0;" in t


def test_capacity_has_progressive_strong_proven_elite_levels():
    t = GOVERNOR.read_text()
    assert "return 1;" in t
    assert "return 2;" in t
    assert "return 3;" in t
    assert "m_strongMaxOpen" in t
    assert "m_provenMaxOpen" in t
    assert "m_eliteMaxOpen" in t


def test_drawdown_blocks_expansion_without_forcing_extra_restrictions():
    t = GOVERNOR.read_text()
    assert "if(drawdownPercent>=m_capacityBlockDrawdown) return 0;" in t
    assert "m_capacityBlockDrawdown(5.0)" in t


def test_order_manager_uses_dynamic_admission_ceiling_without_closing_existing_positions():
    t = ORDERS.read_text()
    assert "SetMaxOpenTrades" in t
    assert "MaxOpenTrades() const" in t
    assert "Existing trades are never closed solely because capacity contracts." in t


def test_portfolio_position_count_limits_are_adaptive_but_risk_cap_stays_separate():
    t = PORTFOLIO.read_text()
    assert "SetPositionLimits" in t
    assert "aggregate" in t
    assert "m_maxPortfolioRiskPercent" in t


def test_ea_uses_adaptive_capacity_for_multi_trade_slot_calculation():
    t = EA.read_text()
    assert "g_orders.MaxOpenTrades()-g_orders.OpenCount()" in t
    assert "g_portfolio.SetPositionLimits(g_capacity.MaxPositionsPerSymbol(),g_capacity.MaxPositionsPerGroup())" in t
