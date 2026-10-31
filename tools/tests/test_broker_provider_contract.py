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
        "SetTypeFillingBySymbol(_Symbol)",
    ):
        assert capability in adapter

    for vendor in (
        "Exness", "Pepperstone", "HFM", "IC Markets", "XM", "IG",
        "OANDA", "AvaTrade", "FXTM", "FP Markets",
    ):
        assert vendor.casefold() not in adapter.casefold()
    assert "provider-agnostic" in policy
    assert "fixed vendor allowlist" in policy
    assert "operator may connect any broker" in contract
    assert "Supporting a non-MT5 venue requires a separate execution adapter" in contract
