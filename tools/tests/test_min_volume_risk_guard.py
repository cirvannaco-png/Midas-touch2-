from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RISK = ROOT / "EA" / "includes" / "Trading" / "RiskEngine.mqh"


def test_risk_sizing_rejects_volume_below_broker_minimum_even_if_override_enabled():
    source = RISK.read_text(encoding="utf-8")
    assert "OrderCalcProfit(" in source
    assert "lots=minLot+MathFloor((lots-minLot)/lotStep)*lotStep" in source
    assert "if(lots<minLot)" in source
    assert "if(lots<minLot)" in source
    block = source.split("if(lots<minLot)", 1)[1].split("\n     }", 1)[0]
    assert "return 0.0;" in block
    assert "lots=minLot;" not in block
    assert "exceededRiskBudget=true;" not in block


def test_account_currency_stop_risk_fails_closed_on_bad_profit_model():
    source = RISK.read_text(encoding="utf-8")
    assert "EstimateStopLossPerLot" in source
    assert "if(!EstimateStopLossPerLot(symbol,entry,stopLoss,lossPerLot))" in source
    assert "if(!MathIsValidNumber(riskAmount) || riskAmount<=0.0)" in source


ORDER_MANAGER = ROOT / "EA" / "includes" / "Execution" / "OrderManager.mqh"


def test_order_manager_rejects_bad_volume_before_allocating_trade_state():
    source = ORDER_MANAGER.read_text(encoding="utf-8")
    helper_start = source.index("bool COrderManager::IsBrokerVolumeValid")
    submit_start = source.index("bool COrderManager::Submit")
    submit = source[submit_start:]
    helper = source[helper_start:submit_start]

    assert "MathIsValidNumber(volume)" in helper
    assert "SYMBOL_VOLUME_MIN" in helper
    assert "SYMBOL_VOLUME_MAX" in helper
    assert "SYMBOL_VOLUME_STEP" in helper
    assert "volume<minLot || volume>maxLot" in helper
    assert "MathRound(steps)" in helper
    assert "if(!IsBrokerVolumeValid(decision.symbol,volume))" in submit
    assert submit.index("if(!IsBrokerVolumeValid(decision.symbol,volume))") < submit.index("ArrayResize(m_trades,idx+1)")
    assert "volume violates broker min/max/step" in submit


def test_order_manager_rejects_invalid_trade_identity_and_side_before_submission():
    source = ORDER_MANAGER.read_text(encoding="utf-8")
    submit = source[source.index("bool COrderManager::Submit"):]
    assert "decision.decision_id<=0" in submit
    assert "decision.setup.type!=ORDER_TYPE_BUY && decision.setup.type!=ORDER_TYPE_SELL" in submit
