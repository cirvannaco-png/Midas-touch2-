import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.dao_wider_stops_experiment import ExperimentError, compare_manifest


ROLES = (
    "A_baseline", "B_wider_initial_sl", "C_wider_trailing", "D_both_wider",
)


def _preset(profile="small_account", arm="A_baseline"):
    p = {
        "InpAccountRiskProfile": "1" if profile == "small_account" else "2",
        "InpSLBufferATR": "0.25",
        "InpMaxSLDistanceATR": "1.5",
        "InpDynamicStopATRMult": "1.5",
        "InpEnableDynamicStop": "true",
    }
    for prefix in ("InpSmall", "InpProp", ""):
        p.update({
            prefix + "RiskPercentPerTrade": "30",
            prefix + "MaxOpenTrades": "1",
            prefix + "MaxDailyLossPercent": "35",
            prefix + "MaxDrawdownPercent": "50",
            prefix + "DeriskStartPercent": "40",
            prefix + "DeriskFloor": "0.5",
            prefix + "MaxPortfolioRiskPercent": "30",
            prefix + "MaxPositionsPerSymbol": "1",
            prefix + "MaxPositionsPerGroup": "1",
        })
    if arm in {"B_wider_initial_sl", "D_both_wider"}:
        p["InpSLBufferATR"] = "0.3125"
        p["InpMaxSLDistanceATR"] = "1.875"
    if arm in {"C_wider_trailing", "D_both_wider"}:
        p["InpDynamicStopATRMult"] = "1.875"
    return p


def _write_set(path, values):
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")


def _write_deals(path, pnl=10):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "position_id", "time", "entry", "volume", "profit",
            "commission", "swap", "fee", "risk_cash",
        ])
        writer.writeheader()
        writer.writerow({
            "position_id": "p1", "time": "2025-01-10T10:00:00Z",
            "entry": "in", "volume": "0.01", "profit": "0",
            "commission": "0", "swap": "0", "fee": "0", "risk_cash": "450",
        })
        writer.writerow({
            "position_id": "p1", "time": "2025-01-10T11:00:00Z",
            "entry": "out", "volume": "0.01", "profit": str(pnl),
            "commission": "0", "swap": "0", "fee": "0", "risk_cash": "0",
        })


def _manifest(tmp_path, *, profile="small_account"):
    dataset = tmp_path / "ticks.bin"
    dataset.write_bytes(b"frozen synthetic test fixture, not market data")
    roles = []
    for role in ROLES:
        preset = tmp_path / f"{role}.set"
        deals = tmp_path / f"{role}.csv"
        _write_set(preset, _preset(profile, role))
        _write_deals(deals, pnl=10 if role != "C_wider_trailing" else 15)
        roles.append({
            "role": role, "input_preset": preset.name, "deals_csv": deals.name,
        })
    manifest = {
        "schema_version": 1,
        "experiment_id": "unit-test-only",
        "dataset_path": dataset.name,
        "test_context": {
            "account_profile": profile, "account_currency": "KES",
            "initial_balance": 1500, "symbol": "EURUSD", "timeframe": "M15",
            "period_start": "2025-01-01T00:00:00Z",
            "period_end": "2025-12-31T23:59:59Z",
            "locked_oos_start": "2025-10-01T00:00:00Z",
            "locked_oos_end": "2025-12-31T23:59:59Z",
            "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            "ea_source_sha": "a" * 40, "ea_build": "test-build",
            "terminal_build": "test-terminal", "fill_policy": "test-policy",
            "spread_model": "real-ticks-plus-stress",
            "spread_widening_multiplier": 1.25,\n            "baseline_spread_points": 10, "cash_per_point_per_lot": 0.1, "slippage_points": 2,
            "base_costs_applied_in_tester": True,
            "stress_costs_applied_in_analysis": True, "swap_included": True,
        },
        "variants": roles,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_four_arm_matched_comparison_reports_only_closed_oos_positions(tmp_path):
    path = _manifest(tmp_path)
    report = compare_manifest(path)
    assert set(report["variants"]) == set(ROLES)
    assert report["variants"]["A_baseline"]["full_period"]["completed_positions"] == 1
    assert report["variants"]["A_baseline"]["locked_oos"]["completed_positions"] == 0
    assert report["variants"]["C_wider_trailing"]["full_period"]["net_pnl"] == 15
    assert report["promotion_recommendation"] is None


def test_rejects_risk_percent_that_is_not_constant_30(tmp_path):
    path = _manifest(tmp_path)
    doc = json.loads(path.read_text())
    preset_path = tmp_path / "B_wider_initial_sl.set"
    preset_path.write_text(preset_path.read_text().replace("InpSmallRiskPercentPerTrade=30", "InpSmallRiskPercentPerTrade=29"))
    path.write_text(json.dumps(doc))
    with pytest.raises(ExperimentError, match="preserve"):
        compare_manifest(path)


def test_rejects_changes_to_entry_or_other_non_stop_settings(tmp_path):
    path = _manifest(tmp_path)
    preset_path = tmp_path / "C_wider_trailing.set"
    with preset_path.open("a") as stream:
        stream.write("InpMinRiskReward=2.0\n")
    # This creates a key-set mismatch rather than silently accepting a confound.
    path.write_text(path.read_text())
    with pytest.raises(ExperimentError, match="key set differs"):
        compare_manifest(path)


def test_rejects_dataset_hash_mismatch(tmp_path):
    path = _manifest(tmp_path)
    (tmp_path / "ticks.bin").write_bytes(b"changed after freeze")
    with pytest.raises(ExperimentError, match="SHA-256"):
        compare_manifest(path)


def test_rejects_missing_closed_position_initial_risk(tmp_path):
    path = _manifest(tmp_path)
    deals = tmp_path / "A_baseline.csv"
    text = deals.read_text().replace('"450"', '"0"')
    deals.write_text(text)
    with pytest.raises(ExperimentError, match="no entry risk_cash"):
        compare_manifest(path)


def test_prop_firm_profile_selector_and_30_percent_are_checked(tmp_path):
    path = _manifest(tmp_path, profile="prop_firm")
    report = compare_manifest(path)
    assert report["context"]["account_profile"] == "prop_firm"
    preset = tmp_path / "D_both_wider.set"
    preset.write_text(preset.read_text().replace("InpPropRiskPercentPerTrade=30", "InpPropRiskPercentPerTrade=25"))
    with pytest.raises(ExperimentError, match="preserve"):
        compare_manifest(path)
