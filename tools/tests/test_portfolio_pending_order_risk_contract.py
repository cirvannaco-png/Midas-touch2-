from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO = ROOT / "EA" / "includes" / "Portfolio" / "PortfolioManager.mqh"


def read_portfolio() -> str:
    return PORTFOLIO.read_text(encoding="utf-8")


def test_portfolio_risk_includes_active_pending_orders():
    source = read_portfolio()
    assert "double CPortfolioManager::PendingOrderRiskAmount(ulong ticket)" in source
    assert "for(int i=0;i<OrdersTotal();i++)" in source
    assert "OrderGetDouble(ORDER_PRICE_OPEN)" in source
    assert "OrderGetDouble(ORDER_SL)" in source
    assert "OrderGetDouble(ORDER_VOLUME_CURRENT)" in source
    assert "(ulong)OrderGetInteger(ORDER_MAGIC)!=m_magic" in source
    assert "totalRisk+=risk" in source
    assert "orderSymbol==symbol" in source
    assert "CorrelationGroup(orderSymbol)==group" in source


def test_pending_order_with_unknown_or_wrong_sided_protection_fails_closed():
    source = read_portfolio()
    assert 'if(symbol=="" || entry<=0.0 || sl<=0.0 || volume<=0.0) return -1.0;' in source
    assert "if(isBuy && sl>=entry) return -1.0;" in source
    assert "if(isSell && sl<=entry) return -1.0;" in source
    assert "if(risk<0.0) unknown=true;" in source
    assert "if(unknown)" in source
    assert "existing position or pending order under this magic number has uncomputable risk" in source


def test_breakeven_or_profit_locked_position_does_not_become_unknown_risk():
    source = read_portfolio()
    assert "if(type==POSITION_TYPE_BUY && sl>=entry) return 0.0;" in source
    assert "if(type==POSITION_TYPE_SELL && sl<=entry) return 0.0;" in source
    assert "Gaps, slippage and broker" in source
    assert "Invalid tick metadata remains unknown, not zero risk." in source


def test_execution_reservation_requires_fresh_account_margin_evidence():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    control = (root / "telegram-bridge/app/execution_control.py").read_text()
    api = (root / "telegram-bridge/app/api/execution_ledger.py").read_text()
    client = (root / "EA/includes/Execution/ExecutionLedgerClient.mqh").read_text()
    ea = (root / "EA/MedisTouch_v2.8.mq5").read_text()

    assert "MAX_MARGIN_SNAPSHOT_AGE_SECONDS = 10.0" in control
    assert "MIN_FREE_MARGIN_BUFFER_RATIO = 0.20" in control
    assert "required_margin" in control and "account_currency" in control
    assert "margin_snapshot_epoch: int = Field(gt=0)" in api
    assert "free_margin: float = Field(gt=0)" in api
    assert "OrderCalcMargin(decision.setup.type" in ea
    assert "ACCOUNT_MARGIN_FREE" in ea
    assert "margin_snapshot_epoch" in client
    assert "required_margin" in client
