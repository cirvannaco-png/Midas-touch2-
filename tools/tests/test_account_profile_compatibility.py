from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
PROFILE_DOC = ROOT / "docs" / "ACCOUNT_PROFILES.md"


def test_existing_prop_firm_defaults_remain_compatibility_baseline():
    source = EA.read_text()
    required_defaults = (
        "input double InpRiskPercentPerTrade=0.5;",
        "input int InpMaxOpenTrades=3;",
        "input double InpMaxDailyLossPercent=3.0;",
        "input double InpMaxDrawdownPercent=10.0;",
        "input double InpDeriskStartPercent=5.0;",
        "input double InpDeriskFloor=0.25;",
        "input double InpMaxPortfolioRiskPercent=3.0;",
        "input int InpMaxPositionsPerSymbol=3;",
        "input int InpMaxPositionsPerGroup=3;",
        "input bool InpAllowMinLotOverride=false;",
    )
    for default in required_defaults:
        assert default in source, f"Existing compatibility default changed or missing: {default}"


def test_micro_account_research_is_documented_as_unvalidated_and_separate():
    doc = PROFILE_DOC.read_text()
    assert "research only" in doc.lower()
    assert "not proven profitable" in doc.lower()
    assert "not been ported into or validated in the production MT5 EA" in doc
    assert "Do not copy the 8% risk" in doc


def test_production_ea_has_not_silently_adopted_micro_research_risk():
    source = EA.read_text()
    # The micro candidate's aggressive parameters belong to the separate
    # StrategyTune research artifact, not the current production EA defaults.
    assert "input double InpRiskPercentPerTrade=8.0;" not in source
    assert "input double InpMaxDailyLossPercent=18.0;" not in source
    assert "input double InpMaxDrawdownPercent=35.0;" not in source
