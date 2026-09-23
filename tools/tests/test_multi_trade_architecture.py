from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
MULTI = ROOT / "EA" / "includes" / "Execution" / "MultiTradeEngine.mqh"
ORDERS = ROOT / "EA" / "includes" / "Execution" / "OrderManager.mqh"
PORTFOLIO = ROOT / "EA" / "includes" / "Portfolio" / "PortfolioManager.mqh"
TRACKER = ROOT / "EA" / "includes" / "Trading" / "OutcomeTrackerLive.mqh"


def test_multi_trade_is_hard_gated_by_calibrated_probability_and_sample():
    t = MULTI.read_text()
    assert "setup.calibration_has_enough_data" in t
    assert "setup.calibration_sample<m_minCalibrationSample" in t
    assert "setup.calibrated_probability<m_dualProbability" in t
    assert "m_dualProbability" in t
    assert "m_tripleProbability" in t


def test_multi_trade_fails_closed_on_non_finite_or_out_of_range_probability_and_confidence():
    t = MULTI.read_text()
    assert "MathIsValidNumber(setup.calibrated_probability)" in t
    assert "setup.calibrated_probability<0.0" in t
    assert "setup.calibrated_probability>100.0" in t
    assert "MathIsValidNumber(setup.confidence)" in t


def test_multi_trade_requires_strong_current_confidence_too():
    t = MULTI.read_text()
    assert "setup.confidence<m_minRawConfidence" in t


def test_multi_trade_uses_heging_semantics_for_independent_legs():
    t = MULTI.read_text()
    assert "ACCOUNT_MARGIN_MODE" in t
    assert "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in t


def test_risk_budget_is_split_across_legs():
    t = MULTI.read_text()
    assert "m_dualRiskFraction0" in t
    assert "m_dualRiskFraction1" in t
    assert "m_tripleRiskFraction0" in t
    assert "m_tripleRiskFraction1" in t
    assert "m_tripleRiskFraction2" in t
    assert "fractionTotal-1.0" in t


def test_portfolio_preflight_is_batch_aware():
    t = PORTFOLIO.read_text()
    assert "AllowNewTradeBatch" in t
    assert "symbolCount+proposedPositions" in t
    assert "groupCount+proposedPositions" in t


def test_order_manager_supports_same_parent_with_distinct_legs():
    t = ORDERS.read_text()
    assert "legIndex" in t
    assert "FindByDecisionAndLeg" in t
    assert "Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,ulong &ticketOut,int legIndex=0)" in t
    assert "HasLiveTradeForDecision" in t


def test_child_closes_do_not_finalize_parent_until_last_live_leg():
    ea = EA.read_text()
    tracker = TRACKER.read_text()
    assert "g_orders.HasLiveTradeForDecision(decisionId,position)" in ea
    assert "p.lots+=volume" in tracker
    assert "m_calibration.Record(p.confidenceAtSignal,p.realizedPnL)" in tracker


def test_ea_wires_multi_trade_after_decision_and_before_order_submission():
    t = EA.read_text()
    assert '#include "includes/Execution/MultiTradeEngine.mqh"' in t
    assert "g_multiTrade.Init(" in t
    assert "MultiTradePlan plan" in t
    assert "g_multiTrade.Build(decision.setup,availableSlots,plan)" in t
    assert "g_portfolio.AllowNewTradeBatch" in t
    assert "g_orders.Submit(legDecision,legLots[leg],InpUseMarketOrders,maxDeviation,ticket,leg)" in t


def test_multi_trade_capacity_supports_three_symbol_positions():
    t = EA.read_text()
    assert "input int InpMaxOpenTrades=3;" in t
    assert "input int InpMaxPositionsPerSymbol=3;" in t
