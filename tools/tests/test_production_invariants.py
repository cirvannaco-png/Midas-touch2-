from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EA=ROOT/"EA"/"MedisTouch_v2.8.mq5"
TRACKER=ROOT/"EA"/"includes"/"Trading"/"OutcomeTrackerLive.mqh"
RISK_GUARD=ROOT/"EA"/"includes"/"Portfolio"/"RiskGuard.mqh"
PORTFOLIO=ROOT/"EA"/"includes"/"Portfolio"/"PortfolioManager.mqh"
BROKER=ROOT/"EA"/"includes"/"Execution"/"BrokerAdapter.mqh"
RECOVERY=ROOT/"EA"/"includes"/"Recovery"/"RecoveryEngine.mqh"
ORDERS=ROOT/"EA"/"includes"/"Execution"/"OrderManager.mqh"
CONFIG_SYNC=ROOT/"EA"/"includes"/"Signals"/"ConfigSync.mqh"
GATING=ROOT/"tools"/"gating.py"
CI=ROOT/".gitlab-ci.yml"

def test_live_tracker_has_decision_identity_and_broker_fill():
    text=TRACKER.read_text()
    assert "void AddSetup(TradeSetup &setup,long decisionId=-1)" in text
    assert "bool MarkExecuted(long id,double fill,datetime t,double volume)" in text
    assert "p.entryFillPrice=fill" in text
    assert "p.fillTime=t" in text

def test_live_tracker_uses_closed_execution_bars_and_excludes_fill_bar():
    text=TRACKER.read_text()
    assert "ctx.candles.GetCandle(1)" in text
    assert "ctx.candles.Timeframe()!=m_entryTF" in text
    assert "if(bar.time<=fillBar)continue" in text

def test_live_tracker_closes_from_broker_deals():
    text=TRACKER.read_text()
    assert "bool MarkClosed" in text
    assert "p.realizedPnL+=netPnl" in text

def test_ea_initializes_tracker_on_chart_execution_timeframe():
    text=EA.read_text()
    assert "g_tracker.Init(&g_logger,_Symbol,_Period" in text
    assert "g_tracker.Update(g_chartCtx);" in text
    assert "g_tracker.Update(g_fvgCtx);" not in text

def test_outcomes_advance_before_entry_gates():
    text=EA.read_text()
    assert text.index("g_tracker.Update(g_chartCtx);") < text.index("g_riskGuard.IsHardHalted")

def test_ea_uses_broker_deal_fill_and_close_events():
    text=EA.read_text()
    assert "g_tracker.MarkExecuted(decisionId,price,dealTime,volume)" in text
    assert "g_tracker.MarkClosed(decisionId,price,dealTime,net,commission,swap,fee,stillOpen,outcome)" in text

def test_ea_fails_closed_on_decision_persistence():
    text=EA.read_text()
    assert "if(!g_store.Save(decision))" in text
    assert "if(!g_store.SaveExecution(decision.decision_id,lots,ticket))" in text

def test_normal_opportunity_floor_is_below_transition_floor():
    text=EA.read_text()
    assert "input double InpMinConfidenceExecute=68.0;" in text
    assert "input double InpMinConfidenceSignal=58.0;" in text

def test_risk_guard_state_is_account_wide():
    text=RISK_GUARD.read_text()
    assert 'string prefix = "MedisTouch_RiskGuard_" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN));' in text
    assert ' + "_" + symbol' not in text

def test_portfolio_fails_closed_on_uncomputable_existing_risk():
    text=PORTFOLIO.read_text()
    assert "if(risk<0.0) unknown=true" in text
    assert "refusing new exposure until its stop/risk can be verified" in text

def test_broker_checks_directional_trade_modes():
    text=BROKER.read_text()
    assert "SYMBOL_TRADE_MODE_LONGONLY" in text
    assert "SYMBOL_TRADE_MODE_SHORTONLY" in text
    assert "SYMBOL_TRADE_MODE_CLOSEONLY" in text

def test_recovery_restores_actual_broker_entry():
    text=RECOVERY.read_text()
    assert "double actualEntry=PositionGetDouble(POSITION_PRICE_OPEN);" in text
    assert "RestoreTrade(dec,currentVolume,ticket,state,actualEntry)" in text

def test_order_manager_exposes_real_fill():
    text=ORDERS.read_text()
    assert "double FillPriceForDecision(long decisionId)" in text
    assert "double m_trades[idx].fillPrice" in text

def test_config_sync_retries_failed_ack():
    text=CONFIG_SYNC.read_text()
    assert "m_lastAckedHash" in text
    assert "will retry on the next poll" in text
    assert "m_lastAckedHash==configHash" in text

def test_gating_requires_all_metrics_to_be_persistent():
    text=GATING.read_text()
    assert "elif incomplete:" in text
    assert "all(persistent_moves[m] == \"up\" for m in GATED_METRICS)" in text
    assert "all(persistent_moves[m] == \"down\" for m in GATED_METRICS)" in text

def test_ci_runs_core_gates_on_main():
    text=CI.read_text()
    assert 'if: \'$CI_COMMIT_BRANCH == "main"\'' in text
    assert "mql5-structure:" in text
    assert "medis-touch-python:" in text
    assert "telegram-bridge:" in text
    assert "telegram-bridge-dependency-audit:" in text
