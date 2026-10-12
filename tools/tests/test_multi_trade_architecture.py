from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
MULTI = ROOT / "EA" / "includes" / "Portfolio" / "MultiTradeEngine.mqh"
EXECUTION_MULTI = ROOT / "EA" / "includes" / "Execution" / "MultiTradeEngine.mqh"
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
    assert "setup.confidence<0.0" in t
    assert "setup.confidence>100.0" in t


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
    assert "Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,double maxRiskCash,ulong &ticketOut,int legIndex=0)" in t
    assert "HasLiveTradeForDecision" in t


def test_child_closes_do_not_finalize_parent_until_last_live_leg():
    ea = EA.read_text()
    tracker = TRACKER.read_text()
    assert "g_orders.HasLiveTradeForDecision(decisionId)" in ea
    assert "g_orders.HasLiveTradeForDecision(decisionId,position)" not in ea
    assert "double nextLots=p.lots+volume" in tracker
    assert "p.lots=nextLots" in tracker
    assert "m_calibration.Record(p.confidenceAtSignal,p.realizedPnL)" in tracker


def test_ea_wires_multi_trade_through_portfolio_before_order_submission():
    t = EA.read_text()
    assert not EXECUTION_MULTI.exists()
    assert '#include "includes/Portfolio/MultiTradeEngine.mqh"' in t
    assert "g_multiTrade.Init(" in t
    assert "MultiTradePlan plan" in t
    build = t.index("g_multiTrade.Build(decision.setup,availableSlots,plan)")
    gate = t.index("g_portfolio.AllowNewTradeBatch", build)
    submit = t.index("g_orders.Submit(legDecision,legLots[leg],InpUseMarketOrders,maxDeviation,legRisk[leg],ticket,leg)", gate)
    assert build < gate < submit


def test_multi_trade_capacity_supports_three_symbol_positions():
    t = EA.read_text()
    assert "input int InpMaxOpenTrades=3;" in t
    assert "input int InpMaxPositionsPerSymbol=3;" in t


def test_order_manager_rejects_invalid_or_over_budget_entries_before_sending():
    t = ORDERS.read_text()
    assert "!MathIsValidNumber(maxRiskCash)" in t
    assert "maxRiskCash<=0.0" in t
    assert "OrderCalcProfit(orderType,decision.symbol,volume,riskEntry,decision.setup.stop_loss,estimatedAtStop)" in t
    assert "estimatedRisk>maxRiskCash+riskTolerance" in t
    assert "IsBrokerVolumeValid(decision.symbol,volume)" in t
    assert "if(ArrayResize(m_trades,idx+1)!=idx+1) return false;" in t


def test_incremental_fill_events_are_deal_idempotent_and_volume_bounded():
    t = ORDERS.read_text()
    ea = EA.read_text()
    assert "FillDealSeen(dealTicket)" in t
    assert "RememberFillDeal(dealTicket)" in t
    assert "nextFilled>m_trades[i].volume+tolerance" in t
    assert "m_trades[i].fillPrice=nextNotional/nextFilled" in t
    assert "g_orders.MarkFilledFromPending(orderTicket,positionIdentifier,positionTicket,price,volume,trans.deal);" in ea


def test_sizing_uses_the_worst_permitted_market_fill_for_both_manual_and_automated_orders():
    t = EA.read_text()
    assert "ConservativeRiskSizingEntry(_Symbol,decision.setup.type,entry,InpUseMarketOrders,maxDeviation)" in t
    assert "ConservativeRiskSizingEntry(_Symbol,setup.type,entry,true,maxDeviation)" in t
    assert "RiskAmountForLots(_Symbol,legLots[leg],sizingEntry,chosen.stop_loss)" in t
    assert "RiskAmountForLots(_Symbol,lots,sizingEntry,setup.stop_loss)" in t


def test_submit_disambiguates_position_ticket_from_stable_ledger_identity():
    orders = ORDERS.read_text(encoding="utf-8")
    broker = (ROOT / "EA" / "includes" / "Execution" / "BrokerAdapter.mqh").read_text(encoding="utf-8")
    submit_start = orders.index("bool COrderManager::Submit(")
    submit_end = orders.index("bool COrderManager::RestoreTrade(", submit_start)
    submit = orders[submit_start:submit_end]

    # BrokerAdapter returns a live ticket when available, but may return a
    # stable identifier or unresolved order token while MT5 catches up.
    # Do not poison the stable identity field with an untyped token.
    assert "ulong             MagicNumber() { return m_magic; }" in broker
    assert "ResolveLivePositionTicket(string symbol,ulong positionIdentifier)" in orders
    assert "PositionGetString(POSITION_SYMBOL)!=symbol" in orders
    assert "PositionGetInteger(POSITION_MAGIC)!=m_broker.MagicNumber()" in orders
    assert "stableIdentifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);" in submit
    assert "if(stableIdentifier>0) m_trades[idx].positionIdentifier=stableIdentifier;" in submit
    assert "m_trades[idx].positionIdentifier=ticket;" not in submit


def test_invalid_entry_deviation_and_nonpositive_worst_fill_fail_closed():
    ea = EA.read_text(encoding="utf-8")
    orders = ORDERS.read_text(encoding="utf-8")
    sizing_start = ea.index("double ConservativeRiskSizingEntry(")
    sizing_end = ea.index("\nvoid OnTick()", sizing_start)
    sizing = ea[sizing_start:sizing_end]
    submit_start = orders.index("bool COrderManager::Submit(")
    submit_end = orders.index("bool COrderManager::RestoreTrade(", submit_start)
    submit = orders[submit_start:submit_end]

    assert "!MathIsValidNumber(maxEntryDeviation) || maxEntryDeviation<0.0" in sizing
    assert "!MathIsValidNumber(maxEntryDeviation) || maxEntryDeviation<0.0" in submit
    assert "if(!MathIsValidNumber(riskEntry) || riskEntry<=0.0) return false;" in submit


def test_recovery_trade_allocation_rejects_invalid_volume_and_failed_resize():
    orders = ORDERS.read_text(encoding="utf-8")
    start = orders.index("bool COrderManager::RestoreTrade(")
    end = orders.index("#endif", start)
    method = orders[start:end]
    assert "!MathIsValidNumber(volume)" in method
    assert "!MathIsValidNumber(fillPrice)" in method
    assert "if(ArrayResize(m_trades,idx+1)!=idx+1) return false;" in method
