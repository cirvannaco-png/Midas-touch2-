from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BROKER = ROOT / "EA/includes/Execution/BrokerAdapter.mqh"
NORMALIZER = ROOT / "EA/includes/Execution/PriceGridNormalizer.mqh"
POSITION_MANAGER = ROOT / "EA/includes/Execution/PositionManager.mqh"


def test_tick_grid_normalizer_has_directional_rounding_and_fail_closed_validation():
    source = NORMALIZER.read_text(encoding="utf-8")
    assert "MathCeil(units-tolerance)" in source
    assert "MathFloor(units+tolerance)" in source
    assert "tickSize<=0.0" in source
    assert "digits<0 || digits>8" in source
    assert "roundUp && normalizedPrice<rawPrice-directionalTolerance" in source
    assert "!roundUp && normalizedPrice>rawPrice+directionalTolerance" in source


def test_broker_adapter_normalizes_prices_before_validation_and_submission():
    source = BROKER.read_text(encoding="utf-8")
    start = source.index("bool CBrokerAdapter::ModifySLTP(ulong ticket,double sl,double tp)")
    end = source.index("bool CBrokerAdapter::ClosePartial", start)
    method = source[start:end]
    assert 'SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE)' in method
    assert 'NormalizePriceToTickGrid(sl,tickSize,digits,!isBuy,adjustedSL)' in method
    assert 'NormalizePriceToTickGrid(tp,tickSize,digits,isBuy,adjustedTP)' in method
    assert 'adjustedSL<=currentSL' in method and 'adjustedSL>=currentSL' in method
    assert 'ValidateStopDistance(symbol,refPrice,adjustedSL,adjustedTP,isBuy,"ModifySLTP")' in method
    assert 'm_trade.PositionModify(ticket,adjustedSL,adjustedTP)' in method
    assert "will not remove a live protective stop" in method


def test_position_audit_records_the_broker_applied_stop_not_raw_candidate():
    source = POSITION_MANAGER.read_text(encoding="utf-8")
    assert "double observedSL=PositionGetDouble(POSITION_SL)" in source
    assert 'm_audit.Record(ticket,dec.symbol,isBuy,EnumToString(ds.stage),curSL,appliedSL,price,r,ds.reason)' in source
