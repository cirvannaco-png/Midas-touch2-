from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
TRACKER = ROOT / "EA" / "includes" / "Trading" / "OutcomeTracker.mqh"
RISK_GUARD = ROOT / "EA" / "includes" / "Portfolio" / "RiskGuard.mqh"
PORTFOLIO = ROOT / "EA" / "includes" / "Portfolio" / "PortfolioManager.mqh"
BROKER = ROOT / "EA" / "includes" / "Execution" / "BrokerAdapter.mqh"
RECOVERY = ROOT / "EA" / "includes" / "Recovery" / "RecoveryEngine.mqh"
ORDERS = ROOT / "EA" / "includes" / "Execution" / "OrderManager.mqh"
CONFIG_SYNC = ROOT / "EA" / "includes" / "Signals" / "ConfigSync.mqh"
GATING = ROOT / "tools" / "gating.py"
CI = ROOT / ".gitlab-ci.yml"


def test_outcome_tracker_has_real_add_setup_definition():
    text = TRACKER.read_text()
    assert "void COutcomeTracker::AddSetup(TradeSetup &setup, long decisionId)" in text
    assert "void COutcomeTracker::AddSetup(TradeSetup &setup, long decisionId)\n  {" in text


def test_outcome_tracker_uses_decision_id_for_fill_identity():
    text = TRACKER.read_text()
    assert "GetFillState(datetime creation_time, long decisionId" in text
    assert "m_pending[i].decisionId != decisionId" in text


def test_outcome_tracker_is_execution_timeframe_only():
    text = TRACKER.read_text()
    assert "executionCtx" in text
    assert "executionCtx.candles.Timeframe() != m_entryTF" in text
    assert "The setup's creation bar is never eligible" in text


def test_ea_initializes_tracker_on_chart_execution_timeframe():
    text = EA.read_text()
    assert "g_tracker.Init(&g_logger,_Symbol,_Period" in text
    assert "g_tracker.Update(g_chartCtx);" in text
    assert "g_tracker.Update(g_fvgCtx);" not in text


def test_lifecycle_lookup_uses_creation_time_and_decision_id():
    text = EA.read_text()
    assert "g_tracker.GetFillState(g_lifecycleCreationTime,g_lifecycleDecisionId" in text


def test_risk_guard_state_is_account_wide():
    text = RISK_GUARD.read_text()
    assert 'string prefix = "MedisTouch_RiskGuard_" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN));' in text
    assert ' + "_" + symbol' not in text


def test_portfolio_fails_closed_on_uncomputable_existing_risk():
    text = PORTFOLIO.read_text()
    assert "if(risk<0.0) unknown=true" in text
    assert "refusing new exposure until its stop/risk can be verified" in text


def test_broker_checks_directional_trade_modes():
    text = BROKER.read_text()
    assert "SYMBOL_TRADE_MODE_LONGONLY" in text
    assert "SYMBOL_TRADE_MODE_SHORTONLY" in text
    assert "SYMBOL_TRADE_MODE_CLOSEONLY" in text


def test_recovery_restores_actual_broker_entry():
    text = RECOVERY.read_text()
    assert "double actualEntry=PositionGetDouble(POSITION_PRICE_OPEN);" in text
    assert "RestoreTrade(dec,currentVolume,ticket,state,actualEntry)" in text


def test_order_manager_exposes_real_fill():
    text = ORDERS.read_text()
    assert "double FillPriceForDecision(long decisionId)" in text
    assert "double m_trades[idx].fillPrice" in text


def test_config_sync_retries_failed_ack():
    text = CONFIG_SYNC.read_text()
    assert "m_lastAckedHash" in text
    assert "will retry on the next poll" in text
    assert "m_lastAckedHash==configHash" in text


def test_gating_requires_all_metrics_to_be_persistent():
    text = GATING.read_text()
    assert "elif incomplete:" in text
    assert "all(persistent_moves[m] == \"up\" for m in GATED_METRICS)" in text
    assert "all(persistent_moves[m] == \"down\" for m in GATED_METRICS)" in text


def test_ci_runs_core_gates_on_main():
    text = CI.read_text()
    assert 'if: \'$CI_COMMIT_BRANCH == "main"\'' in text
    assert "mql5-structure:" in text
    assert "medis-touch-python:" in text
    assert "telegram-bridge:" in text
    assert "telegram-bridge-dependency-audit:" in text
