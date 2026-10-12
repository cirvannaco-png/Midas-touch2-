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

def test_enabled_atr_distance_cap_fails_closed_without_valid_atr():
    source = RISK.read_text(encoding="utf-8")
    start = source.index("bool CRiskEngine::ValidateSetupAtEntry")
    end = source.index("\n  }\n#endif", start)
    body = source[start:end]

    # maxSLDistanceATR == 0 is the explicit opt-out. A negative limit is invalid,
    # and an enabled cap cannot be considered satisfied if ATR is unavailable.
    assert "if(maxSLDistanceATR<0.0)" in body
    assert "if(maxSLDistanceATR>0.0)" in body
    assert "if(currentATR<=0.0)" in body
    assert body.index("if(currentATR<=0.0)") < body.index("double slDistATR=slDist/currentATR;")
    assert "if(currentATR>0.0 && maxSLDistanceATR>0.0)" not in body
