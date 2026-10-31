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
        assert token in adapter or token in read(ROOT / "EA" / "includes" / "Execution" / "PriceGridNormalizer.mqh")


def test_symbol_specific_filling_policy_is_set_for_every_trade_path():
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
        assert "m_trade.SetTypeFillingBySymbol(symbol);" in method_body(adapter, method), method

    assert "m_trade.SetTypeFillingBySymbol(_Symbol);" in adapter  # harmless chart default; request paths override it
