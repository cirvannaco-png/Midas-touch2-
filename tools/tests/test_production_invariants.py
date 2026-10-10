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
TRADE_ZONE=ROOT/"EA"/"includes"/"Trading/StrategyTradeZone.mqh"
GATING=ROOT/"tools"/"gating.py"
CI=ROOT/".gitlab-ci.yml"


def test_live_tracker_has_decision_identity_and_broker_fill():
    t=TRACKER.read_text();assert 'void AddSetup(TradeSetup &setup,long decisionId=-1,string decisionFingerprint="")' in t;assert "bool MarkExecuted(long id,double fill,datetime t,double volume)" in t;assert "p.entryFillPrice=fill" in t;assert "p.fillTime=t" in t

def test_live_tracker_uses_closed_execution_bars_and_excludes_fill_bar():
    t=TRACKER.read_text();assert "ctx.candles.GetCandle(1)" in t;assert "ctx.candles.Timeframe()!=m_entryTF" in t;assert "if(bar.time<=fillBar)continue" in t

def test_live_tracker_closes_from_broker_deals():
    t=TRACKER.read_text();assert "bool MarkClosed" in t;assert "p.realizedPnL+=netPnl" in t

def test_restart_restores_tracker_state():
    t=RECOVERY.read_text();assert "m_tracker.RestoreExecuted(restoredDecision.setup,decisionId,actualEntry" in t;assert "g_activeOutcomeTracker" in t

def test_ea_initializes_tracker_on_chart_execution_timeframe():
    t=EA.read_text();assert "g_tracker.Init(&g_logger,_Symbol,_Period" in t;assert "g_tracker.Update(g_chartCtx);" in t;assert "g_tracker.Update(g_fvgCtx);" not in t

def test_ea_restores_config_sync_timer_callback():
    t=EA.read_text();assert "EventSetTimer(MathMax(60,InpConfigSyncPollMinutes*60));" in t;assert "void OnTimer(){if(StringLen(InpConfigSyncEndpoint)>0)g_configSync.Poll();}" in t

def test_outcomes_advance_before_entry_gates():
    t=EA.read_text();assert t.index("g_tracker.Update(g_chartCtx);")<t.index("g_riskGuard.IsHardHalted")

def test_ea_uses_broker_deal_fill_and_close_events():
    t=EA.read_text();assert "g_tracker.MarkExecuted(decisionId,price,dealTime,volume)" in t;assert "g_tracker.MarkClosed(decisionId,price,dealTime,net,commission,swap,fee,stillOpen,outcome)" in t

def test_partial_close_keeps_current_position_live_for_tracker():
    t=EA.read_text()
    assert "bool stillOpen=g_orders.HasLiveTradeForDecision(decisionId);" in t
    assert "g_orders.HasLiveTradeForDecision(decisionId,position)" not in t

def test_ea_fails_closed_on_decision_persistence():
    t=EA.read_text()
    assert "if(!g_store.Save(decision))" in t
    assert "g_store.SaveExecution(decision.decision_id,legLots[leg],ticket,leg,plan.target[leg])" in t

def test_decision_store_persists_thesis_invalidation_and_strategy():
    t=DECISION_STORE.read_text();assert "p[5]=DoubleToString(rec.setup.invalidation,_Digits)" in t;assert "p[14]=IntegerToString((int)rec.setup.reasons.selected_strategy)" in t;assert "rec.setup.invalidation=StringToDouble(f[5])" in t;assert "rec.setup.reasons.selected_strategy=(ENUM_SELECTED_STRATEGY)(int)StringToInteger(f[14])" in t

def test_legacy_decisions_do_not_fabricate_invalidation():
    t=DECISION_STORE.read_text();assert "rec.setup.invalidation=0.0" in t;assert "Legacy decisions predate the first-class thesis boundary" in t

def test_strategy_trade_zone_fail_closed_paths_do_not_return_temporary_structs():
    t=TRADE_ZONE.read_text()
    assert "TradeSetup out;ZeroMemory(out);" in t
    assert "m_lastSetup=out;return out;" in t
    assert "return TradeSetup();" not in t

def test_strategy_trade_zone_applies_spread_floor_then_rechecks_invalidation():
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
    t=RECOVERY.read_text()
    assert "double actualEntry=PositionGetDouble(POSITION_PRICE_OPEN);" in t
    assert "RestoreTrade(restoredDecision,currentVolume,ticket,state,actualEntry,legIndex)" in t

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


def test_signal_enqueue_persists_signal_and_outbox_atomically():
    """A valid signal must commit its durable signal row and outbox row together."""
    t=(ROOT/"telegram-bridge"/"tests"/"test_routes.py").read_text()
    assert "session.add(outbox)" in (ROOT/"telegram-bridge"/"app"/"routes.py").read_text()
    assert "await session.commit()" in (ROOT/"telegram-bridge"/"app"/"routes.py").read_text()
    assert "SignalDeliveryOutbox" in t


def test_signal_enqueue_suppressed_path_has_no_delivery_outbox():
    """Suppressed broadcasts still record the signal but must not enqueue delivery."""
    t=(ROOT/"telegram-bridge"/"app"/"routes.py").read_text()
    assert 'details="Broadcast paused or symbol muted - signal recorded, not sent to Telegram."' in t

 
def test_recovery_matches_execution_metadata_by_decision_and_leg():
    t=RECOVERY.read_text()
    assert "execs[e].decision_id==decisionId && execs[e].leg_index==legIndex" in t
    assert "restoredDecision.setup.final_tp=restoredTarget" in t
    assert "m_orders.RestoreTrade(restoredDecision,currentVolume,ticket,state,actualEntry,legIndex)" in t
 
def test_execution_store_persists_leg_index_and_target():
    t=DECISION_STORE.read_text()
    assert "IntegerToString(rec.leg_index)" in t
    assert "DoubleToString(rec.target,_Digits)" in t
    assert "rec.leg_index=(n>4)?(int)StringToInteger(f[4]):0" in t
    assert "rec.target=(n>5)?StringToDouble(f[5]):0.0" in t
 
def test_outcome_tracker_aggregates_risk_across_child_fills():
    t=(ROOT/"EA"/"includes"/"Trading"/"OutcomeTrackerLive.mqh").read_text()
    assert "p.weightedRiskDistLots=p.riskDist*volume" in t
    assert "p.weightedRiskDistLots+=MathAbs(fill-p.setup.stop_loss)*volume" in t
    assert "p.weightedRiskDistLots>0.0?p.weightedRiskDistLots" in t

def test_position_modify_requires_trade_server_confirmation():
    """CTrade's bool return is a request-check result, not proof the server applied SLTP."""
    broker=(ROOT/"EA"/"includes"/"Execution"/"BrokerAdapter.mqh").read_text()
    assert "submitted && m_trade.ResultRetcode()==TRADE_RETCODE_DONE" in broker
    assert "ModifySLTP was not confirmed by the trade server" in broker


def test_partial_and_full_closes_require_confirmed_server_result():
    broker=(ROOT/"EA"/"includes"/"Execution"/"BrokerAdapter.mqh").read_text()
    assert "submitted && (code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL)" in broker
    assert "submitted && code==TRADE_RETCODE_DONE" in broker
    assert "ClosePartial was not confirmed by the trade server" in broker
    assert "CloseFull was not confirmed by the trade server" in broker

def test_position_manager_resolves_mutable_ticket_from_stable_position_identifier():
    orders=(ROOT/"EA"/"includes"/"Execution"/"OrderManager.mqh").read_text()
    manager=(ROOT/"EA"/"includes"/"Execution"/"PositionManager.mqh").read_text()
    assert "ulong                positionIdentifier;" in orders
    assert "PositionTicketAt(int idx)" in orders
    assert "POSITION_IDENTIFIER)==identifier" in orders
    assert "ArchiveClosedPosition(ulong positionIdentifier)" in orders
    assert "ulong ticket=m_orders.PositionTicketAt(i);" in manager
    assert "m_orders.ArchiveClosedPosition(positionIdentifier);" in manager
    assert "COrderManager::PositionIdentifierIsOpen" not in orders


def test_market_order_submission_does_not_assume_accepted_means_filled():
    broker=(ROOT/"EA"/"includes"/"Execution"/"BrokerAdapter.mqh").read_text()
    orders=(ROOT/"EA"/"includes"/"Execution"/"OrderManager.mqh").read_text()
    ea=EA.read_text()
    assert "bool &fillConfirmedOut" in broker
    assert "fillConfirmedOut=false;" in broker
    assert "if(fillConfirmed)" in orders
    assert "awaiting confirmed deal event" in orders
    assert "MarkFilledFromPending(orderTicket,position,price,volume)" in ea


def test_partial_fills_refresh_live_position_volume_and_average_entry():
    orders=(ROOT/"EA"/"includes"/"Execution"/"OrderManager.mqh").read_text()
    assert "Additional partial fills for the same broker order" in orders
    assert "m_trades[i].volume=PositionGetDouble(POSITION_VOLUME);" in orders
    assert "double actualEntry=PositionGetDouble(POSITION_PRICE_OPEN);" in orders
    assert "if(actualEntry>0.0)m_trades[i].fillPrice=actualEntry;" in orders

def test_unfilled_accepted_orders_release_capacity_when_cancelled_or_expired():
    orders=(ROOT/"EA"/"includes"/"Execution"/"OrderManager.mqh").read_text()
    ea=EA.read_text()
    assert "MarkCancelledOrder(ulong orderTicket)" in orders
    assert "g_orders.MarkCancelledOrder(trans.order)" in ea
    assert "ORDER_STATE_CANCELED" in ea
    assert "ORDER_STATE_EXPIRED" in ea
    assert "ORDER_STATE_REJECTED" in ea


def test_mql5_position_identity_methods_are_part_of_architecture_contract():
    validator=(ROOT/"tools"/"validate_mql5_architecture.py").read_text()
    orders=(ROOT/"EA"/"includes"/"Execution"/"OrderManager.mqh").read_text()
    assert '"MarkFilledFromPending": 4' in validator
    assert '"MarkCancelledOrder": 1' in validator
    assert "PositionTicketAt(int idx)" in orders
    assert "PositionIdentifierAt(int idx)" in orders

def test_partial_exit_obeys_hedging_mode_and_broker_volume_grid():
    broker=(ROOT/"EA"/"includes"/"Execution"/"BrokerAdapter.mqh").read_text()
    manager=(ROOT/"EA"/"includes"/"Execution"/"PositionManager.mqh").read_text()
    assert "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in broker
    assert "SYMBOL_VOLUME_STEP" in broker
    assert "MathFloor((bounded/step)+1e-9)" in broker
    assert "remainder<minVolume-1e-10" in broker
    assert "m_partialCloseSupported=(AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)" in manager
    assert "m_partialCloseSupported && stateAfterStop==TS_PROTECTED" in manager


def test_metaeditor_preflight_stages_and_compiles_all_mql5_entry_points():
    script=(ROOT/"tools"/"compile_mt5.ps1").read_text()
    stager=(ROOT/"tools"/"stage_mt5_package.py").read_text()
    assert "tools/stage_mt5_package.py" in script
    assert "MedisTouch_v2.8.mq5" in script
    assert "MedisTouch_Indicator_v2.8.mq5" in script
    assert "ConfigSyncContract.mq5" in script
    assert "DecisionEngineGeometry.mq5" in script
    assert "DynamicStopEngine.mq5" in script
    assert "--test-destination $testRoot" in script
    assert 'parser.add_argument("--test-destination"' in stager
    assert "test_entry_points = sorted(test_source_dir.glob(\"*.mq5\"))" in stager
    assert "/compile:" in script and '"/log"' in script and "/inc:" in script
    assert '$metaLogPath = [System.IO.Path]::ChangeExtension($SourcePath, ".log")' in script
    assert "Copy-Item -LiteralPath $metaLogPath -Destination $LogPath -Force" in script
    assert "zero compile errors" in script
    assert "Remove-Item -LiteralPath $binaryPath" in script


def test_active_live_guards_and_dynamic_stop_defaults_are_explicit():
    ea=EA.read_text()
    dynamic=(ROOT/"EA"/"includes"/"Execution"/"DynamicStopInputs.mqh").read_text()
    assert "InpEnableExecution=true" in ea
    assert "InpTrackOutcomes=true" in ea
    assert "InpMaxDailyLossPercent=3.0" in ea
    assert "InpMaxDrawdownPercent=10.0" in ea
    assert "InpMaxPortfolioRiskPercent=3.0" in ea
    assert "InpMaxCorrelationGroupRiskPercent=2.5" in ea
    assert "InpEnableDynamicStop = true" in dynamic
    assert "InpDynamicStopActivateAtR = 0.75" in dynamic
    assert "InpDynamicStopBreakevenAtR = 1.00" in dynamic

def test_netting_accounts_cannot_overlap_same_symbol_decisions():
    orders=(ROOT/"EA"/"includes"/"Execution"/"OrderManager.mqh").read_text()
    assert "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in orders
    assert "if(OpenCount()>0)" in orders
    assert "PositionGetString(POSITION_SYMBOL)==decision.symbol" in orders
    assert "OrderGetString(ORDER_SYMBOL)==decision.symbol" in orders
    assert "one managed decision at a time is required on netting/exchange accounts" in orders


def test_terminal_trade_identity_is_retained_for_delayed_close_events():
    orders=(ROOT/"EA"/"includes"/"Execution"/"OrderManager.mqh").read_text()
    assert "Retain terminal identity records briefly" in orders
    assert "now-terminalAt<300" in orders
    assert "fsm.LastChange()" in orders
