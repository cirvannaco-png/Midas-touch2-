import re
from pathlib import Path


def test_broker_execution_is_provider_agnostic_and_uses_live_mt5_capabilities() -> None:
    root = Path(__file__).resolve().parents[2]
    adapter = (root / "EA/includes/Execution/BrokerAdapter.mqh").read_text(encoding="utf-8")
    policy = (root / "skills/execution-auditor/SKILL.md").read_text(encoding="utf-8")
    contract = (root / "docs/BROKER_COMPATIBILITY.md").read_text(encoding="utf-8")

    # MT5 runtime symbol metadata, not a vendor allowlist, defines capability.
    for capability in (
        "SYMBOL_TRADE_MODE",
        "SYMBOL_TRADE_STOPS_LEVEL",
        "SYMBOL_TRADE_FREEZE_LEVEL",
    ):
        assert capability in adapter

    # Filling policy must be resolved from each instrument immediately before
    # a deal request; a chart-symbol default is unsafe for multi-symbol EAs.
    assert "bool CBrokerAdapter::ConfigureSymbolFilling(string symbol)" in adapter
    assert "SymbolSelect(symbol,true)" in adapter
    assert "!m_trade.SetTypeFillingBySymbol(symbol)" in adapter
    assert "SetTypeFillingBySymbol(_Symbol)" not in adapter
    for method in ("MarketBuy", "MarketSell", "PlaceLimit", "ClosePartial", "CloseFull"):
        start = adapter.index(f"bool CBrokerAdapter::{method}(")
        end = adapter.find("//+------------------------------------------------------------------+", start)
        assert "ConfigureSymbolFilling(symbol)" in adapter[start:end], method

    # Match complete vendor names only; e.g. "IG" must not match "ambiguous".
    vendor_allowlist = re.compile(
        r"\b(?:Exness|Pepperstone|HFM|IC Markets|XM|IG|OANDA|AvaTrade|FXTM|FP Markets)\b",
        re.IGNORECASE,
    )
    assert vendor_allowlist.search(adapter) is None
    assert "provider-agnostic" in policy
    assert "fixed vendor allowlist" in policy
    assert "operator may connect any broker" in contract
    assert "Supporting a non-MT5 venue requires a separate execution adapter" in contract
