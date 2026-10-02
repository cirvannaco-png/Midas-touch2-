from pathlib import Path
import re

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
    assert re.search(r"TradeSetup\s+out;\s*ZeroMemory\(out\);",t)
    assert re.search(r"m_lastSetup\s*=\s*out;\s*return\s+out;",t)
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


def test_dynamic_stop_cannot_widen_structural_risk():
    t=(ROOT/"EA"/"includes"/"Execution"/"DynamicStopEngine.mqh").read_text()
    assert "bool IsTighter" in t
    assert "candidate would widen or equal current stop" in t
    assert "IsTighter(isBuy,candidate,currentSL)" in t


def test_reject_and_wait_are_logged_instead_of_disappearing():
    t=EA.read_text()
    assert "REJECT/WAIT is first-class telemetry" in t
    assert "g_logger.LogSetup(buySetup" in t
    assert "g_logger.LogSetup(sellSetup" in t
    assert "setup.decision_state!=DECISION_TRADE" in t


def test_risk_class_controls_sizing_without_replacing_structural_invalidation():
    t=EA.read_text()
    assert "RiskClassSizingMultiplier(chosen.risk_class)" in t
    cfg=(ROOT/"EA"/"includes"/"Core"/"Config.mqh").read_text()
    assert "RISK_CLASS_HIGH_CONVICTION: return 1.00" in cfg
    assert "RISK_CLASS_STANDARD:        return 0.75" in cfg
    assert "RISK_CLASS_MINIMAL:         return 1.00" in cfg


def test_pending_signal_checks_structural_invalidation():
    t=EA.read_text()
    assert "g_lifecycleSetup.invalidation" in t
    assert "Structural thesis invalidation was crossed before entry" in t


def test_provenance_is_published():
    t=(ROOT/"EA"/"includes"/"Signals"/"SignalPublisher.mqh").read_text()
    for token in (
        "liquidity_scope",
        "liquidity_archetype",
        "sweep_penetration_atr",
        "sweep_rejection_ratio",
        "displacement_atr",
        "bos_distance_atr",
        "fvg_causal",
        "invalidation_distance_atr",
        "regime_id",
    ):
        assert token in t


def test_noncausal_fvg_is_degraded_not_falsely_causal():
    t=(ROOT/"EA"/"includes"/"Decision/DecisionQuality.mqh").read_text()
    assert "STRUCTURE_STAGE_FVG_NONCAUSAL" in t
    assert "bool degraded=(!r.fvg_causal" in t


def test_bos_age_is_persisted_in_provenance():
    s=(ROOT/"EA"/"includes"/"Analysis/Scoring.mqh").read_text()
    p=(ROOT/"EA"/"includes"/"Signals/SignalPublisher.mqh").read_text()
    assert "out.bos_age_bars" in s
    assert "bos_age_bars" in p


def test_risk_class_requires_expected_return_when_calibrated():
    t=(ROOT/"EA"/"includes"/"Decision/DecisionQuality.mqh").read_text()
    assert "setup.expected_return_r" in t
    assert "expected_return_r>0.25" in t
    assert "expected_return_r>0.0" in t

def test_partial_exit_does_not_close_setup_lifecycle():
    t=(ROOT/"EA"/"includes"/"Trading"/"OutcomeTracker.mqh").read_text()
    partial=t[t.index("void COutcomeTracker::ApplyPartial"):t.index("bool COutcomeTracker::IntrabarReplayGeneric")]
    final=t[t.index("void COutcomeTracker::FinalizeExit"):t.index("bool COutcomeTracker::ResolveOrder")]
    assert "SETUP_CLOSED" not in partial
    assert "SETUP_MANAGED" in partial
    assert "SETUP_CLOSED" in final
    live=(ROOT/"EA"/"includes"/"Trading"/"OutcomeTrackerLive.mqh").read_text()
    assert "p.setup.setup_lifecycle=SETUP_CLOSED" in live


def test_strategy_absence_becomes_reject_not_inactive_setup():
    t=(ROOT/"EA"/"includes"/"Trading"/"StrategyTradeZone.mqh").read_text()
    assert "TradeSetup CTradeDecision::BuildRejected" in t
    assert "decision_state=DECISION_REJECT" in t
    assert "setup_lifecycle=SETUP_EXPIRED" in t


def test_signal_logger_persists_decision_provenance():
    t=(ROOT/"EA"/"includes"/"Core"/"SignalLogger.mqh").read_text()
    for token in ("DecisionState", "BlockingLayer", "DecisionReason", "QualityScore", "Lifecycle", "ExpectedReturnR", "RegimeID"):
        assert token in t
