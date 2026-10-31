"""Regression contracts for provider-neutral MT5 execution."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "EA" / "includes" / "Execution" / "BrokerAdapter.mqh"
AUDITOR_SKILL = ROOT / "skills" / "execution-auditor" / "SKILL.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def method_body(source: str, method: str) -> str:
    marker = f"bool CBrokerAdapter::{method}("
    start = source.index(marker)
    end = source.find("//+------------------------------------------------------------------+", start)
    return source[start:] if end < 0 else source[start:end]


def test_mt5_adapter_has_no_fixed_broker_brand_whitelist():
    adapter = read(ADAPTER)
    skill = read(AUDITOR_SKILL)

    assert '#include <Trade\\Trade.mqh>' in adapter
    assert "fixed brand whitelist" in skill
    for brand in ("Exness", "Pepperstone", "HFM", "IC Markets", "OANDA"):
        assert brand not in adapter
        assert brand not in skill


def test_execution_capabilities_are_discovered_from_the_selected_symbol():
    adapter = read(ADAPTER)
    risk = read(ROOT / "EA" / "includes" / "Trading" / "RiskEngine.mqh")
    availability = read(ROOT / "EA" / "includes" / "Core" / "BrokerMarketAvailability.mqh")
    portfolio = read(ROOT / "EA" / "includes" / "Portfolio" / "OpposingPositionPolicy.mqh")
    capabilities = adapter + risk + availability + portfolio

    for token in (
        "SYMBOL_TRADE_MODE",
        "SYMBOL_TRADE_STOPS_LEVEL",
        "SYMBOL_TRADE_FREEZE_LEVEL",
        "SYMBOL_TRADE_TICK_SIZE",
        "SYMBOL_TRADE_TICK_VALUE",
        "SYMBOL_VOLUME_MIN",
        "SYMBOL_VOLUME_MAX",
        "SYMBOL_VOLUME_STEP",
        "SymbolInfoSessionTrade",
        "ACCOUNT_MARGIN_MODE",
    ):
        assert token in capabilities


def test_symbol_specific_filling_policy_is_resolved_fail_closed_for_every_trade_path():
    adapter = read(ADAPTER)

    for method in (
        "MarketBuy",
        "MarketSell",
        "PlaceLimit",
        "CancelOrder",
        "ModifySLTP",
        "ClosePartial",
        "CloseFull",
    ):
        assert "ConfigureSymbolFilling(symbol)" in method_body(adapter, method), method

    configure = method_body(adapter, "ConfigureSymbolFilling")
    assert "SymbolSelect(symbol,true)" in configure
    assert "!m_trade.SetTypeFillingBySymbol(symbol)" in configure
    assert "request rejected" in configure
    assert "SetTypeFillingBySymbol(_Symbol)" not in adapter
