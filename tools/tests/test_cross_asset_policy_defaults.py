from pathlib import Path

ROOT = Path(__file__).parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
INDICATOR = ROOT / "EA" / "MedisTouch_Indicator_v2.8.mq5"
KEY_LEVELS = ROOT / "EA" / "includes" / "SmartMoney" / "ExtendedKeyLevels.mqh"
RISK = ROOT / "EA" / "includes" / "Trading" / "RiskEngine.mqh"
PORTFOLIO = ROOT / "EA" / "includes" / "Portfolio" / "PortfolioManager.mqh"
BROKER = ROOT / "EA" / "includes" / "Execution" / "BrokerAdapter.mqh"
ORDERS = ROOT / "EA" / "includes" / "Execution" / "OrderManager.mqh"


def test_fx_session_filter_is_opt_in():
    text = EA.read_text(encoding="utf-8")
    assert "input bool InpUseSessionFilter=false;" in text
    assert "London/NY is a liquidity policy, not a universal exchange calendar" in text


def test_indicator_matches_multi_asset_session_default():
    text = INDICATOR.read_text(encoding="utf-8")
    assert "input bool   InpUseSessionFilter = false;" in text
    assert "London/NY is a liquidity policy, not a universal exchange calendar" in text


def test_psychological_price_grid_is_not_xau_hardcoded():
    ea = EA.read_text(encoding="utf-8")
    levels = KEY_LEVELS.read_text(encoding="utf-8")
    assert "input double InpKeyLevelRoundStep=0.0;" in ea
    assert "m_roundStep(0.0)" in levels
    assert "Configure(double roundStep = 0.0)" in levels
    assert "if(m_roundStep <= 0.0) return false;" in levels
    assert "single-symbol XAUUSD" not in levels


def test_risk_sizing_uses_mt5_account_currency_profit_model():
    text = RISK.read_text(encoding="utf-8")
    for token in (
        "OrderCalcProfit(",
        "EstimateStopLossPerLot",
        "ACCOUNT_EQUITY",
        "SYMBOL_VOLUME_MIN",
        "SYMBOL_VOLUME_MAX",
        "SYMBOL_VOLUME_STEP",
        "MathFloor(lots/lotStep",
    ):
        assert token in text


def test_risk_validation_requires_directional_sl_tp_geometry():
    text = RISK.read_text(encoding="utf-8")
    assert "if(!(sl<entry && tp1>entry)) return false;" in text
    assert "if(!(sl>entry && tp1<entry)) return false;" in text
    assert "setup.tp2>0.0 && setup.tp2<=entry" in text
    assert "setup.final_tp>0.0 && setup.final_tp<=entry" in text
    assert "setup.tp2>0.0 && setup.tp2>=entry" in text
    assert "setup.final_tp>0.0 && setup.final_tp>=entry" in text


def test_minimum_lot_override_emits_explicit_risk_warning():
    text = EA.read_text(encoding="utf-8")
    assert "RISK BUDGET OVERRIDE:" in text
    assert "Disable InpAllowMinLotOverride to preserve strict sizing." in text


def test_market_orders_size_and_validate_at_worst_allowed_fill():
    ea = EA.read_text(encoding="utf-8")
    risk = RISK.read_text(encoding="utf-8")
    assert "bool CRiskEngine::ValidateSetupAtEntry(" in risk
    assert "sizingEntry=(chosen.type==ORDER_TYPE_BUY)?entry+deviation:entry-deviation;" in ea
    assert "ValidateSetupAtEntry(chosen,sizingEntry,InpMinRiskReward,InpMaxSLDistanceATR,atr)" in ea
    assert "InpRiskPercentPerTrade*fraction,sizingEntry,chosen.stop_loss" in ea
    assert "RiskAmountForLots(_Symbol,legLots[leg],sizingEntry,chosen.stop_loss)" in ea


def test_portfolio_risk_includes_open_pending_orders():
    text = PORTFOLIO.read_text(encoding="utf-8")
    assert "double PendingOrderRiskAmount(ulong ticket);" in text
    assert "for(int i=0;i<OrdersTotal();i++)" in text
    assert "ORDER_VOLUME_CURRENT" in text
    assert "PendingOrderRiskAmount(ticket)" in text
    assert "position or pending order under this magic number has uncomputable risk" in text


def test_final_target_cannot_be_missing_or_negative():
    text = RISK.read_text(encoding="utf-8")
    assert "setup.final_tp<=0.0 || setup.tp2<0.0" in text


def test_broker_mutations_require_server_retcode_confirmation():
    text = BROKER.read_text(encoding="utf-8")
    for method in ("CancelOrder", "ModifySLTP", "ClosePartial", "CloseFull"):
        start = text.index(f"CBrokerAdapter::{method}(")
        body = text[start:]
        body = body[:body.index("\n//+------------------------------------------------------------------+") if "\n//+------------------------------------------------------------------+" in body else len(body)]
        assert "LastRequestOk(" in body, f"{method} must inspect the broker retcode"
        assert "serverAccepted" in body, f"{method} must not rely on the CTrade bool alone"


def test_placed_retcode_is_not_treated_as_completed_mutation():
    text = BROKER.read_text(encoding="utf-8")
    assert "if(code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL) return true;" in text
    assert 'if(code==TRADE_RETCODE_PLACED &&' in text
    assert '(action=="PlaceLimit" || action=="MarketBuy" || action=="MarketSell")) return true;' in text


def test_market_request_without_fill_remains_pending_for_reconciliation():
    broker = BROKER.read_text(encoding="utf-8")
    orders = ORDERS.read_text(encoding="utf-8")
    assert "fillPriceOut=(dealTicket>0 ? m_trade.ResultPrice() : 0.0);" in broker
    assert "fill not confirmed" in orders
    assert "if(fillPrice>0.0)" in orders
    assert "MarkFilledFromPending" in orders
