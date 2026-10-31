import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.compare_mt5_variant_runs import ComparisonError, compare_manifest


ROLES = ("baseline_dual_lane", "strict_filter_dual_lane", "strict_only")


def _context(dataset_hash):
    return {
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "period_start": "2025-01-01T00:00:00Z",
        "period_end": "2026-01-01T00:00:00Z",
        "locked_oos_start": "2025-11-01T00:00:00Z",
        "locked_oos_end": "2025-12-01T00:00:00Z",
        "dataset_sha256": dataset_hash,
        "ea_source_sha": "a" * 40,
        "ea_build": "build-1",
        "terminal_build": "terminal-1",
        "data_vendor": "Generic MT5 test feed",
        "spread_model": "real_ticks",
        "spread_points": None,
        "commission_per_lot": 7.0,
        "slippage_points": 2.0,
        "fill_policy": "real_ticks",
        "initial_balance": 10000.0,
        "risk_percent": 0.5,
        "account_currency": "USD",
        "leverage": "1:500",
    }


def _write_deals(path: Path, *, with_lane=True, profits=(5.0, -20.0)):
    columns = ["position_id", "time", "entry", "volume", "profit", "commission", "swap", "fee", "risk_cash"]
    if with_lane:
        columns.append("lane")
    rows = [
        ["P1", "2025-09-05T10:00:00Z", "in", 1, 0, -1, 0, 0, 100],
        ["P1", "2025-09-05T11:00:00Z", "out", 1, profits[0], -1, 0, 0, 100],
        ["P2", "2025-10-05T10:00:00Z", "in", 1, 0, -1, 0, 0, 100],
        ["P2", "2025-10-05T11:00:00Z", "out", 1, profits[1], -1, 0, 0, 100],
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for index, row in enumerate(rows):
            if with_lane:
                # P1 is the fallback lane, P2 the strict lane, which exercises
                # lane-specific aggregation instead of merely checking a header.
                row.append("FALLBACK" if index < 2 else "STRICT")
            writer.writerow(row)


def _make_manifest(folder: Path, *, lane=True):
    folder.mkdir(parents=True, exist_ok=True)
    dataset_path = folder / "dataset.bin"
    dataset_path.write_bytes(b"fixed tick-data export for test")
    dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    context = _context(dataset_hash)
    variants = []
    for i, role in enumerate(ROLES):
        preset = folder / f"{role}.set"
        preset.write_text(f"InpMagicNumber={10+i}\nInpRiskPercent=0.5\n", encoding="utf-8")
        report = folder / f"{role}.html"
        report.write_text(f"<html>MT5 report for {role}</html>\n", encoding="utf-8")
        deals = folder / f"{role}_deals.csv"
        _write_deals(deals, with_lane=lane)
        open_positions = folder / f"{role}_open.csv"
        open_positions.write_text("position_id\n", encoding="utf-8")
        variants.append({
            "role": role,
            "run_id": f"run-{i+1}",
            "observed_context": dict(context),
            "parameters": {"InpRiskPercent": 0.5, "InpMagicNumber": 10+i},
            "input_preset": preset.name,
            "report_path": report.name,
            "deals_csv": deals.name,
            "open_positions_csv": open_positions.name,
        })
    manifest_path = folder / "manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "experiment_id": "matched-2025-gold-m5",
        "test_context": context,
        "dataset_path": dataset_path.name,
        "variants": variants,
    }, indent=2), encoding="utf-8")
    return manifest_path


def test_matched_run_comparison_hashes_artifacts_and_reports_oos_deltas(tmp_path):
    manifest = _make_manifest(tmp_path)
    report, summary = compare_manifest(manifest)

    assert summary["matched_context_verified"] is True
    assert summary["dataset_digest_verified"] is True
    assert report["comparison_only"] is True
    assert report["promotion_recommendation"] is None
    baseline = report["variants"]["baseline_dual_lane"]
    assert baseline["metrics"]["development"]["completed_positions"] == 2
    assert "locked_oos" not in baseline["metrics"]
    full = baseline["metrics"]["development"]
    assert full["average_win_R"] == 0.03
    assert full["average_loss_R_abs"] == 0.22
    assert full["payoff_ratio_R"] == 0.1364
    assert full["break_even_win_rate_pct_from_avg_R"] == 88.0
    assert "payoff_ratio_R" in report["candidate_deltas_vs_baseline"]["strict_only"]["development_delta"]
    assert baseline["artifacts"]["report"]["sha256"]
    assert "locked_oos_delta" not in report["candidate_deltas_vs_baseline"]["strict_only"]


def test_mismatched_observed_context_is_rejected(tmp_path):
    manifest_path = _make_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["variants"][1]["observed_context"]["risk_percent"] = 0.7
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ComparisonError, match="risk_percent"):
        compare_manifest(manifest_path)


def test_lane_attribution_is_required_for_separate_lane_reporting(tmp_path):
    manifest_path = _make_manifest(tmp_path, lane=False)

    with pytest.raises(ComparisonError, match="needs a lane"):
        compare_manifest(manifest_path)


def test_input_presets_must_have_distinct_hashes(tmp_path):
    manifest_path = _make_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first = manifest_path.parent / manifest["variants"][0]["input_preset"]
    duplicate = manifest_path.parent / manifest["variants"][1]["input_preset"]
    duplicate.write_bytes(first.read_bytes())
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ComparisonError, match="identical input-preset"):
        compare_manifest(manifest_path)


def test_all_three_predeclared_variants_are_required(tmp_path):
    manifest_path = _make_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["variants"] = manifest["variants"][:-1]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ComparisonError, match="strict_only"):
        compare_manifest(manifest_path)


def test_dataset_digest_is_verified_against_bytes(tmp_path):
    manifest_path = _make_manifest(tmp_path)
    dataset = tmp_path / "dataset.bin"
    dataset.write_bytes(dataset.read_bytes() + b"tampered")
    with pytest.raises(ComparisonError, match="does not match"):
        compare_manifest(manifest_path)


def test_empty_strict_only_run_is_reported_without_inventing_metrics(tmp_path):
    manifest_path = _make_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    variant = next(item for item in manifest["variants"] if item["role"] == "strict_only")
    deals = tmp_path / variant["deals_csv"]
    deals.write_text(
        "position_id,time,entry,volume,profit,commission,swap,fee,risk_cash,lane\n",
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report, _ = compare_manifest(manifest_path)
    metrics = report["variants"]["strict_only"]["metrics"]["development"]
    assert metrics["completed_positions"] == 0
    assert metrics["net_expectancy_per_completed_position"] is None

def test_lane_metrics_are_reported_separately(tmp_path):
    manifest = _make_manifest(tmp_path)
    report, _ = compare_manifest(manifest)
    lanes = report["variants"]["baseline_dual_lane"]["metrics"]["development"]["by_lane"]
    assert set(lanes) == {"FALLBACK", "STRICT"}
    assert lanes["FALLBACK"]["positions"] == 1
    assert lanes["STRICT"]["positions"] == 1

def test_default_comparison_withholds_locked_oos_outcomes_and_diagnostics(tmp_path):
    manifest_path = _make_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    variant = next(item for item in manifest["variants"] if item["role"] == "strict_only")
    deals = tmp_path / variant["deals_csv"]
    with deals.open("a", encoding="utf-8") as stream:
        stream.write("P3,2025-11-08T10:00:00Z,in,0.5,0,-1,0,0,100,STRICT\n")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report, _ = compare_manifest(manifest_path)
    metrics = report["variants"]["strict_only"]["metrics"]["development"]
    diagnostics = report["variants"]["strict_only"]["ledger_diagnostics"]
    assert metrics["completed_positions"] == 2
    assert "locked_oos" not in report["variants"]["strict_only"]["metrics"]
    assert not any("locked_oos" in key for key in diagnostics)
    assert report["locked_oos_status"].startswith("withheld")


def test_cost_columns_must_be_explicit_even_when_the_values_are_zero(tmp_path):
    manifest_path = _make_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    deals_path = manifest_path.parent / manifest["variants"][0]["deals_csv"]
    with deals_path.open("r", newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        fieldnames = [name for name in reader.fieldnames if name != "swap"]
    with deals_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: value for key, value in row.items() if key in fieldnames} for row in rows)
    with pytest.raises(ComparisonError, match="explicitly export commission, swap, and fee"):
        compare_manifest(manifest_path)


def test_spread_model_must_be_reproducible(tmp_path):
    manifest_path = _make_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["test_context"]["spread_model"] = "unknown"
    for variant in manifest["variants"]:
        variant["observed_context"]["spread_model"] = "unknown"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ComparisonError, match="spread_model must be real_ticks or fixed_points"):
        compare_manifest(manifest_path)


def test_fixed_spread_model_requires_a_positive_point_value(tmp_path):
    manifest_path = _make_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["test_context"]["spread_model"] = "fixed_points"
    for variant in manifest["variants"]:
        variant["observed_context"]["spread_model"] = "fixed_points"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ComparisonError, match="requires spread_points > 0"):
        compare_manifest(manifest_path)
