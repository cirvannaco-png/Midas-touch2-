from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
PANEL = ROOT / "EA" / "includes" / "UI" / "TradeControlPanel.mqh"
STOP_INPUTS = ROOT / "EA" / "includes" / "Execution" / "DynamicStopInputs.mqh"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_chart_panel_exposes_required_operator_controls():
    panel = read(PANEL)
    for action in ("BUY", "SELL", "CLOSE ALL", "EMERGENCY STOP", "RESUME"):
        assert action in panel


def test_emergency_stop_is_persisted_and_blocks_new_entries():
    ea = read(EA)
    assert "GlobalVariableSet(EmergencyStopGlobalKey(),1.0)" in ea
    assert "if(g_emergencyStop)return;" in ea
    assert "GlobalVariableDel(EmergencyStopGlobalKey())" in ea


def test_manual_orders_use_risk_controls_and_normal_order_manager():
    ea = read(EA)
    assert "g_risk.ValidateSetup(setup,InpMinRiskReward,InpMaxSLDistanceATR,atr)" in ea
    assert "g_risk.CalculateLotSize(_Symbol,InpRiskPercentPerTrade" in ea
    assert "g_portfolio.AllowNewTradeBatch(_Symbol,proposedRisk,1,portfolioReason)" in ea
    assert "g_orders.Submit(decision,lots,true,maxDeviation,ticket,0)" in ea
    assert "g_store.SaveExecution(decision.decision_id,lots,ticket,0,setup.final_tp)" in ea


def test_close_controls_are_scoped_to_symbol_and_magic():
    ea = read(EA)
    assert "PositionGetString(POSITION_SYMBOL)!=_Symbol" in ea
    assert "(ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagicNumber" in ea
    assert "g_orders.CancelPendingAt(i)" in ea


def test_custom_sessions_are_configurable_and_applied_to_new_entries():
    ea = read(EA)
    for name in (
        "InpUseCustomTradingSessions",
        "InpSession1Start",
        "InpSession1End",
        "InpSession2Start",
        "InpSession2End",
        "InpSession3Start",
        "InpSession3End",
    ):
        assert name in ea
    assert "if(!IsConfiguredSessionAllowed())" in ea
    assert "SessionWindowContains" in ea


def test_trailing_profit_is_enabled_by_default_and_visible_on_panel():
    stop_inputs = read(STOP_INPUTS)
    panel = read(PANEL)
    assert "input bool   InpEnableDynamicStop = true" in stop_inputs
    assert "Trailing profit: %s" in panel
    assert "InpEnableDynamicStop" in read(EA)


def test_execution_audit_records_orders_fills_and_closes_to_csv_and_terminal():
    audit = read(PANEL)
    ea = read(EA)
    assert "MidasTouch_ExecutionAudit_" in audit
    assert "FileWrite(handle" in audit
    assert 'g_execAudit.Log("ORDER_SUBMITTED"' in ea
    assert 'g_execAudit.Log("FILL_IN"' in ea
    assert 'g_execAudit.Log("FILL_OUT"' in ea
    assert "PrintFormat(\"MidasTouch AUDIT" in audit



def test_emergency_stop_remains_recoverable_and_resume_requires_flat_exposure():
    ea = read(EA)
    assert "InpShowTradeControlPanel || g_emergencyStop" in ea
    assert "bool HasManagedExposure()" in ea
    assert "if(HasManagedExposure())" in ea
    assert '"EMERGENCY_RESUME_BLOCKED"' in ea
    assert "g_controlPanel.Destroy();\n      g_panelInitialized=false;" in ea



def test_manual_target_levels_satisfy_the_configured_minimum_rr():
    ea = read(EA)
    manual_start = ea.index("void ManualMarketEntry(bool isBuy)")
    manual_end = ea.index("void OnChartEvent(", manual_start)
    manual_path = ea[manual_start:manual_end]
    # ValidateSetup compares the stop distance to TP1, so TP1 must itself
    # clear the configured minimum R multiple before the order is submitted.
    assert "double tp1R=InpMinRiskReward+0.1;" in manual_path
    assert "double tp2R=(tp1R+InpManualRiskReward)*0.5;" in manual_path
    assert "InpManualRiskReward<InpMinRiskReward+0.3" in manual_path


def test_operator_session_filter_is_an_explicit_header_dependency():
    ea = read(EA)
    assert '#include "includes/Core/SessionFilter.mqh"' in ea


def test_manual_orders_obey_the_same_dst_aware_session_gate():
    ea = read(EA)
    assert "CSessionFilter g_operatorSessionFilter;" in ea
    assert "g_operatorSessionFilter.Configure(InpUseSessionFilter,InpAllowTokyoSession" in ea
    manual_start = ea.index("void ManualMarketEntry(bool isBuy)")
    manual_end = ea.index("void OnChartEvent(", manual_start)
    assert "if(!g_operatorSessionFilter.IsAllowed())" in ea[manual_start:manual_end]


def test_operator_trades_do_not_pollute_strategy_learning():
    ea = read(EA)
    manual_start = ea.index("void ManualMarketEntry(bool isBuy)")
    manual_end = ea.index("void OnChartEvent(", manual_start)
    manual_path = ea[manual_start:manual_end]
    assert "manual_operator" in manual_path
    assert "g_execAudit.Log(\"MANUAL_ORDER_SUBMITTED\"" in manual_path
    assert "g_tracker.AddSetup(" not in manual_path
    assert "ACCOUNT_MODE_WARNING" in ea


def test_manual_buttons_fail_closed_on_netting_symbol_exposure():
    ea = read(EA)
    assert "bool HasAnyChartSymbolExposure()" in ea
    assert "OrderGetString(ORDER_SYMBOL)==_Symbol" in ea
    assert "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING && HasAnyChartSymbolExposure()" in ea
    assert "netting/exchange account already has same-symbol position or pending order" in ea


def test_automated_entries_fail_closed_on_netting_symbol_exposure():
    ea = read(EA)
    assert "bool IsNettingOrExchangeAccount()" in ea
    assert "if(IsNettingOrExchangeAccount() && HasAnyChartSymbolExposure())" in ea
    assert '"AUTOMATED_BLOCKED_NETTING_EXPOSURE"' in ea
