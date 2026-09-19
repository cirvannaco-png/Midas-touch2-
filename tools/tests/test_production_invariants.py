from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EA=ROOT/"EA"/"MedisTouch_v2.8.mq5"
TRACKER=ROOT/"EA"/"includes"/"Trading"/"OutcomeTrackerLive.mqh"
RISK_GUARD=ROOT/"EA"/"includes"/"Portfolio"/"RiskGuard.mqh"
PORTFOLIO=ROOT/"EA"/"includes"/"Portfolio"/"PortfolioManager.mqh"
BROKER=ROOT/"EA"/"includes"/"Execution"/"BrokerAdapter.mqh"
RECOVERY=ROOT/"EA"/"includes"/"Recovery/RecoveryEngine.mqh"
ORDERS=ROOT/"EA"/"includes"/"Execution/OrderManager.mqh"
CONFIG_SYNC=ROOT/"EA"/"includes"/"Signals/ConfigSync.mqh"
DECISION_STORE=ROOT/"EA"/"includes"/"Decision/DecisionStore.mqh"
TRADE_ZONE=ROOT/"EA"/"includes"/"Trading/TradeZone.mqh"
GATING=ROOT/"tools"/"gating.py"
CI=ROOT/".gitlab-ci.yml"


def test_live_tracker_has_decision_identity_and_broker_fill():
    t=TRACKER.read_text();assert "void AddSetup(TradeSetup &setup,long decisionId=-1,string decisionFingerprint=\"")" in t;assert "bool MarkExecuted(long id,double fill,datetime t,double volume)" in t;assert "p.entryFillPrice=fill" in t;assert "p.fillTime=t" in t

def test_live_tracker_uses_closed_execution_bars_and_excludes_fill_bar():
    t=TRACKER.read_text();assert "ctx.candles.GetCandle(1)" in t;assert "ctx.candles.Timeframe()!=m_entryTF" in t;assert "if(bar.time<=fillBar)continue" in t

def test_live_tracker_closes_from_broker_deals():
    t=TRACKER.read_text();assert "bool MarkClosed" in t;assert "p.realizedPnL+=netPnl" in t

def test_restart_restores_tracker_state():
    t=RECOVERY.read_text();assert "m_tracker->RestoreExecuted(dec.setup,decisionId,actualEntry" in t or "m_tracker.RestoreExecuted(dec.setup,decisionId,actualEntry" in t;assert "g_activeOutcomeTracker" in t

def test_ea_initializes_tracker_on_chart_execution_timeframe():
    t=EA.read_text();assert "g_tracker.Init(&g_logger,_Symbol,_Period" in t;assert "g_tracker.Update(g_chartCtx);" in t;assert "g_tracker.Update(g_fvgCtx);" not in t

def test_ea_restores_config_sync_timer_callback():
    t=EA.read_text();assert "EventSetTimer(MathMax(60,InpConfigSyncPollMinutes*60));" in t;assert "void OnTimer(){if(StringLen(InpConfigSyncEndpoint)>0)g_configSync.Poll();}" in t

def test_outcomes_advance_before_entry_gates():
    t=EA.read_text();assert t.index("g_tracker.Update(g_chartCtx);")<t.index("g_riskGuard.IsHardHalted")

def test_ea_uses_broker_deal_fill_and_close_events():
    t=EA.read_text();assert "g_tracker.MarkExecuted(decisionId,price,dealTime,volume)" in t;assert "g_tracker.MarkClosed(decisionId,price,dealTime,net,commission,swap,fee,stillOpen,outcome)" in t

def test_ea_fails_closed_on_decision_persistence():
    t=EA.read_text();assert "if(!g_store.Save(decision))" in t;assert "if(!g_store.SaveExecution(decision.decision_id,lots,ticket))" in t

def test_decision_store_persists_thesis_invalidation_and_strategy():
    t=DECISION_STORE.read_text();assert "p[5]=DoubleToString(rec.setup.invalidation,_Digits)" in t;assert "p[14]=IntegerToString((int)rec.setup.reasons.selected_strategy)" in t;assert "rec.setup.invalidation=StringToDouble(f[5])" in t;assert "rec.setup.reasons.selected_strategy=(ENUM_SELECTED_STRATEGY)(int)StringToInteger(f[14])" in t

def test_legacy_decisions_do_not_fabricate_invalidation():
    t=DECISION_STORE.read_text();assert "rec.setup.invalidation=0.0" in t;assert "Legacy decisions predate the first-class thesis boundary" in t

def test_trade_zone_fail_closed_paths_do_not_return_temporary_structs():
    t=TRADE_ZONE.read_text();assert "TradeSetup rejected;ZeroMemory(rejected);return rejected;" in t;assert "return TradeSetup();" not in t

def test_trade_zone_applies_spread_floor_then_rechecks_invalidation():
    t=TRADE_ZONE.read_text();assert "out.stop_loss=EnforceSpreadFloor" in t;assert "out.stop_loss>=out.invalidation" in t;assert "out.stop_loss<=out.invalidation" in t

def test_normal_opportunity_floor_is_below_transition_floor():
    t=EA.read_text();assert "input double InpMinConfidenceExecute=68.0;" in t;assert "input double InpMinConfidenceSignal=58.0;" in t

def test_risk_guard_state_is_account_wide():
    t=RISK_GUARD.read_text();assert 'string prefix = "MedisTouch_RiskGuard_" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN));' in t;assert ' + "_" + symbol' not in t

def test_portfolio_fails_closed_on_uncomputable_existing_risk():
    t=PORTFOLIO.read_text();assert "if(risk<0.0) unknown=true" in t;assert "refusing new exposure until its stop/risk can be verified" in t

def test_broker_checks_directional_trade_modes():
    t=BROKER.read_text();assert "SYMBOL_TRADE_MODE_LONGONLY" in t;assert "SYMBOL_TRADE_MODE_SHORTONLY" in t;assert "SYMBOL_TRADE_MODE_CLOSEONLY" in t

def test_broker_retries_only_explicit_transient_codes():
    t=BROKER.read_text();assert "case TRADE_RETCODE_REQUOTE:" in t;assert "case TRADE_RETCODE_CONNECTION:" in t;assert "case TRADE_RETCODE_TIMEOUT:" in t;assert "default:" in t;assert "return false;" in t

def test_recovery_restores_actual_broker_entry():
    t=RECOVERY.read_text();assert "double actualEntry=PositionGetDouble(POSITION_PRICE_OPEN);" in t;assert "RestoreTrade(dec,currentVolume,ticket,state,actualEntry)" in t

def test_order_manager_exposes_real_fill():
    t=ORDERS.read_text();assert "FillPrice" in t;assert "fillPrice" in t

def test_config_sync_retries_failed_ack():
    t=CONFIG_SYNC.read_text();assert "m_lastAckedHash" in t;assert "will retry on the next poll" in t;assert "m_lastAckedHash==configHash" in t

def test_gating_requires_all_metrics_to_be_persistent():
    t=GATING.read_text();assert "elif incomplete:" in t;assert "all(persistent_moves[m] == \"up\" for m in GATED_METRICS)" in t;assert "all(persistent_moves[m] == \"down\" for m in GATED_METRICS)" in t

def test_ci_runs_core_gates_on_main():
    t=CI.read_text();assert '$CI_DEFAULT_BRANCH' in t or '$CI_COMMIT_BRANCH == "main"' in t;assert "mql5-structure:" in t;assert "medis-touch-python:" in t;assert "telegram-bridge-dependency-audit:" in t;assert "governance-tests:" in t

def test_ci_governance_gate_contains_repository_and_bridge_checks():
    t=CI.read_text();assert 'PYTHONPATH="$CI_PROJECT_DIR/telegram-bridge:$CI_PROJECT_DIR/tools" pytest -v tools/tests' in t;assert 'ruff check telegram-bridge/app/ telegram-bridge/migrations/ telegram-bridge/scripts/ telegram-bridge/tests/' in t;assert 'bandit -r telegram-bridge/app/ telegram-bridge/scripts/ -q' in t;assert 'telegram-bridge/tests/test_*.py' in t;assert 'render_sync_secrets.py --dry-run' in t
