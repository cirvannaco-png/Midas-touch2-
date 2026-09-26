from pathlib import Path

ROOT = Path(__file__).parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
INDICATOR = ROOT / "EA" / "MedisTouch_Indicator_v2.8.mq5"
KEY_LEVELS = ROOT / "EA" / "includes" / "SmartMoney" / "ExtendedKeyLevels.mqh"
RISK = ROOT / "EA" / "includes" / "Trading" / "RiskEngine.mqh"


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


def test_risk_sizing_uses_symbol_native_trade_properties():
    text = RISK.read_text(encoding="utf-8")
    for token in (
        "SYMBOL_TRADE_TICK_SIZE",
        "SYMBOL_TRADE_TICK_VALUE",
        "SYMBOL_VOLUME_MIN",
        "SYMBOL_VOLUME_MAX",
        "SYMBOL_VOLUME_STEP",
    ):
        assert token in text
