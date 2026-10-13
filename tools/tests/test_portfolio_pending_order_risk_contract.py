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
