from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FVG = ROOT / "EA" / "includes" / "SmartMoney" / "FVG.mqh"


def test_fvg_invalidates_bullish_zone_on_close_through_far_edge():
    t = FVG.read_text()
    assert "if(cd.close < zone.bottom)" in t
    assert "zone.state = FVG_INVALIDATED;" in t


def test_fvg_invalidates_bearish_zone_on_close_through_far_edge():
    t = FVG.read_text()
    assert "if(cd.close > zone.top)" in t


def test_fvg_mitigation_and_invalidation_are_directionally_symmetric():
    t = FVG.read_text()
    bullish = t.index("if(zone.dir == FVG_BULL)")
    bearish = t.index("else", bullish)
    block = t[bullish:bearish]
    assert "cd.close < zone.bottom" in block
    assert "cd.close >= zone.top" in block
    assert "if(cd.close > zone.top)" in t[bearish:]
    assert "cd.close <= zone.bottom" in t[bearish:]


def test_fvg_invalidated_state_is_not_tradeable_by_existing_consumers():
    trade_zone = (ROOT / "EA" / "includes" / "Trading" / "StrategyTradeZone.mqh").read_text()
    visuals = (ROOT / "EA" / "includes" / "UI" / "Visuals.mqh").read_text()
    assert "z.state!=FVG_FRESH&&z.state!=FVG_TESTED" in trade_zone.replace(" ", "")
    assert "z.state != FVG_FRESH && z.state != FVG_TESTED" in visuals
