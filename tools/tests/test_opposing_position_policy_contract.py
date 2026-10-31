from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
POLICY = ROOT / "EA" / "includes" / "Portfolio" / "OpposingPositionPolicy.mqh"
NATIVE_TEST = ROOT / "EA" / "tests" / "OpposingPositionPolicy.mq5"
WORKFLOW = ROOT / ".github" / "workflows" / "mql5-compile.yml"
DEMO_GATE = ROOT / "docs" / "MT5_HEDGING_DUAL_DIRECTION_DEMO_GATE.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ea_routes_opposing_exposure_through_the_tested_policy():
    ea = read(EA)
    policy = read(POLICY)
    assert '#include "includes/Portfolio/OpposingPositionPolicy.mqh"' in ea
    assert "MidasIsOpposingPositionDirection(desiredType,current)" in ea
    assert "MidasIsOpposingOrderDirection(desiredType,current)" in ea
    assert "MidasConcurrentOpposingPolicyAllows(" in ea
    assert "InpAllowConcurrentOpposingPositions" in ea
    assert "HasForeignChartSymbolExposure()" in ea
    assert "AUTOMATED_BLOCKED_FOREIGN_EXPOSURE" in ea
    assert "MANUAL_BLOCKED_FOREIGN_EXPOSURE" in ea
    assert "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in policy
    assert "ACCOUNT_MARGIN_MODE_RETAIL_NETTING" not in policy  # every non-hedging mode fails closed


def test_native_policy_test_covers_both_directions_and_all_mt5_margin_modes():
    test = read(NATIVE_TEST)
    for token in (
        "BUY candidate recognizes existing SELL position",
        "SELL candidate recognizes existing BUY position",
        "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING",
        "ACCOUNT_MARGIN_MODE_RETAIL_NETTING",
        "ACCOUNT_MARGIN_MODE_EXCHANGE",
        "hedging account blocks opposite exposure by default",
        "retail-netting account blocks independent opposing positions even when enabled",
    ):
        assert token in test


def test_native_policy_test_is_compiled_and_executed_in_strategy_tester():
    workflow = read(WORKFLOW)
    assert "Compile opposing-position policy test with MetaEditor" in workflow
    assert "'OpposingPositionPolicy'" in workflow
    assert '"$testName tests: 0 failure(s)"' in workflow or '$testName tests: 0 failure(s)' in workflow
    assert 'PrintFormat("OpposingPositionPolicy tests: %d failure(s)",failures);' in read(NATIVE_TEST)


def test_demo_protocol_keeps_broker_validation_separate_from_policy_ci():
    gate = read(DEMO_GATE)
    assert "not yet run against an operator-selected MT5 demo terminal" in gate
    assert "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in gate
    assert "InpSmallMaxOpenTrades=3" in gate
    assert "two distinct position identifiers/tickets" in gate
    assert "No scenario should be run on live capital" in gate
