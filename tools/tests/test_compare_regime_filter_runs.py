import csv
import hashlib
import json
from pathlib import Path

import pytest

try:
    from tools.compare_regime_filter_runs import MatchedTrailingError, compare_manifest
except ImportError:
    from compare_regime_filter_runs import MatchedTrailingError, compare_manifest


def _context(digest):
    return {
        "symbol": "XAUUSD", "timeframe": "M15",
        "period_start": "2025-01-01T00:00:00Z",
        "period_end": "2026-01-01T00:00:00Z",
        "locked_oos_start": "2025-10-01T00:00:00Z",
        "locked_oos_end": "2025-12-01T00:00:00Z",
        "dataset_sha256": digest, "ea_source_sha": "b" * 40,
        "ea_build": "same-build", "terminal_build": "same-terminal",
        "data_vendor": "Exness", "spread_model": "real_ticks", "spread_points": None,
        "commission_per_lot": 7.0, "slippage_points": 2.0, "fill_policy": "real_ticks",
        "initial_balance": 10000.0, "risk_percent": 0.5,
        "account_currency": "USD", "leverage": "1:500",
    }


def _make_manifest(folder: Path, *, extra_setting=False):
    folder.mkdir(parents=True, exist_ok=True)
    dataset = folder / "ticks.bin"
    dataset.write_bytes(b"synthetic fixture only, never actual OOS data")
    context = _context(hashlib.sha256(dataset.read_bytes()).hexdigest())
    variants = []
    for role, enabled in (("regime_filter_off", "false"), ("regime_filter_on", "true")):
        preset = folder / f"{role}.set"
        settings = [
            f"InpRequireTrendingRegime={enabled}||N",
            "InpDynamicStopUseHTFReferenceLevels=false||N",
            "InpDynamicStopUseWeeklyReference=true||N",
            "InpDynamicStopUseMonthlyReference=true||N",
            "InpRiskPercentPerTrade=0.5||0.1||0.1||1.0||N",
        ]
        if extra_setting and role == "regime_filter_on":
            settings = [s.replace("InpRiskPercentPerTrade=0.5", "InpRiskPercentPerTrade=0.7") for s in settings]
        preset.write_text("\n".join(settings) + "\n", encoding="utf-8")
        report = folder / f"{role}.html"
        report.write_text(f"synthetic report {role}\n", encoding="utf-8")
        deals = folder / f"{role}_deals.csv"
        with deals.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["position_id", "time", "entry", "volume", "profit", "commission", "swap", "fee"])
            writer.writerow(["P1", "2025-09-05T10:00:00Z", "in", 1.0, 0.0, -1.0, 0.0, 0.0])
            writer.writerow(["P1", "2025-09-05T11:00:00Z", "out", 1.0, 5.0, -1.0, 0.0, 0.0])
            writer.writerow(["P2", "2025-10-05T10:00:00Z", "in", 1.0, 0.0, -1.0, 0.0, 0.0])
            writer.writerow(["P2", "2025-10-05T11:00:00Z", "out", 1.0, -20.0, -1.0, 0.0, 0.0])
            writer.writerow(["P3", "2025-11-30T10:00:00Z", "in", 1.0, 0.0, -1.0, 0.0, 0.0])
            writer.writerow(["P3", "2025-12-03T11:00:00Z", "out", 1.0, 10.0, -1.0, 0.0, 0.0])
        opens = folder / f"{role}_open.csv"
        opens.write_text("position_id\n", encoding="utf-8")
        variants.append({
            "role": role, "run_id": "run-" + role,
            "observed_context": dict(context),
            "input_preset": preset.name, "report_path": report.name,
            "deals_csv": deals.name, "open_positions_csv": opens.name,
        })
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "experiment_id": "synthetic-regime-filter-contract",
        "test_context": context, "dataset_path": dataset.name, "variants": variants,
    }, indent=2), encoding="utf-8")
    return manifest


def test_regime_filter_pair_is_matched_and_cost_inclusive(tmp_path):
    report = compare_manifest(_make_manifest(tmp_path))
    assert report["only_effective_set_difference"] == "InpRequireTrendingRegime"
    assert report["matched_context_verified"] is True
    assert report["promotion_recommendation"] is None
    assert report["variants"]["regime_filter_off"]["metrics"]["locked_oos"]["completed_positions"] == 2
    assert report["on_minus_off_deltas"]["locked_oos"]["net_pnl"] == 0


def test_regime_pair_rejects_any_second_setting_change(tmp_path):
    with pytest.raises(MatchedTrailingError, match="only InpRequireTrendingRegime may differ"):
        compare_manifest(_make_manifest(tmp_path, extra_setting=True))


def test_regime_pair_requires_htf_trailing_off_in_both_presets(tmp_path):
    manifest = _make_manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    preset = tmp_path / payload["variants"][1]["input_preset"]
    preset.write_text(preset.read_text(encoding="utf-8").replace(
        "InpDynamicStopUseHTFReferenceLevels=false",
        "InpDynamicStopUseHTFReferenceLevels=true"
    ), encoding="utf-8")
    with pytest.raises(MatchedTrailingError, match="requires InpDynamicStopUseHTFReferenceLevels=false"):
        compare_manifest(manifest)
