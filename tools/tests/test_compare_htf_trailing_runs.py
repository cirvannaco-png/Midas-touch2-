import csv
import hashlib
import json
from pathlib import Path

import pytest

try:
    from tools.compare_htf_trailing_runs import MatchedTrailingError, compare_manifest
except ImportError:
    from compare_htf_trailing_runs import MatchedTrailingError, compare_manifest


def _context(digest):
    return {
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "period_start": "2025-01-01T00:00:00Z",
        "period_end": "2026-01-01T00:00:00Z",
        "locked_oos_start": "2025-10-01T00:00:00Z",
        "locked_oos_end": "2025-12-01T00:00:00Z",
        "dataset_sha256": digest,
        "ea_source_sha": "a" * 40,
        "ea_build": "build-matched",
        "terminal_build": "terminal-matched",
        "data_vendor": "Exness",
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


def _write_deals(path: Path):
    rows = [
        ["P1", "2025-09-05T10:00:00Z", "in", 1.0, 0.0, -1.0, 0.0, 0.0],
        ["P1", "2025-09-05T11:00:00Z", "out", 1.0, 5.0, -1.0, 0.0, 0.0],
        ["P2", "2025-10-05T10:00:00Z", "in", 1.0, 0.0, -1.0, 0.0, 0.0],
        ["P2", "2025-10-05T11:00:00Z", "out", 1.0, -20.0, -1.0, 0.0, 0.0],
        ["P3", "2025-11-30T10:00:00Z", "in", 1.0, 0.0, -1.0, 0.0, 0.0],
        ["P3", "2025-12-03T11:00:00Z", "out", 1.0, 10.0, -1.0, 0.0, 0.0],
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["position_id", "time", "entry", "volume", "profit", "commission", "swap", "fee"])
        writer.writerows(rows)


def _make_manifest(folder: Path, *, add_setting_difference=None, omit_swap=False):
    folder.mkdir(parents=True, exist_ok=True)
    dataset = folder / "ticks.bin"
    dataset.write_bytes(b"synthetic fixture only - not trading data")
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    context = _context(digest)
    variants = []
    for role in ("htf_trailing_off", "htf_trailing_on"):
        on = role == "htf_trailing_on"
        preset = folder / f"{role}.set"
        settings = [
            f"InpDynamicStopUseHTFReferenceLevels={'true' if on else 'false'}||N",
            "InpDynamicStopUseWeeklyReference=true||N",
            "InpDynamicStopUseMonthlyReference=true||N",
            "InpRiskPercentPerTrade=0.5||0.1||0.1||1.0||N",
        ]
        if add_setting_difference and role == add_setting_difference[0]:
            key, value = add_setting_difference[1], add_setting_difference[2]
            settings = [
                f"{key}={value}||N" if line.startswith(key + "=") else line
                for line in settings
            ]
            if not any(line.startswith(key + "=") for line in settings):
                settings.append(f"{key}={value}||N")
        preset.write_text("\n".join(settings) + "\n", encoding="utf-8")
        report = folder / f"{role}.html"
        report.write_text(f"synthetic fixture report {role}\n", encoding="utf-8")
        deals = folder / f"{role}_deals.csv"
        _write_deals(deals)
        if omit_swap:
            rows = list(csv.DictReader(deals.open("r", newline="", encoding="utf-8")))
            fields = [f for f in rows[0] if f != "swap"]
            with deals.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows({k: row[k] for k in fields} for row in rows)
        open_ids = folder / f"{role}_open.csv"
        open_ids.write_text("position_id\n", encoding="utf-8")
        variants.append({
            "role": role,
            "run_id": f"run-{role}",
            "observed_context": dict(context),
            "input_preset": preset.name,
            "report_path": report.name,
            "deals_csv": deals.name,
            "open_positions_csv": open_ids.name,
        })
    manifest_path = folder / "manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "experiment_id": "synthetic-htf-toggle-contract-only",
        "test_context": context,
        "dataset_path": dataset.name,
        "variants": variants,
    }, indent=2), encoding="utf-8")
    return manifest_path


def test_valid_matched_pair_hashes_files_and_reports_cost_inclusive_metrics(tmp_path):
    report = compare_manifest(_make_manifest(tmp_path), include_locked_oos=True)
    assert report["matched_context_verified"] is True
    assert report["dataset_digest_verified"] is True
    assert report["only_effective_set_difference"] == "InpDynamicStopUseHTFReferenceLevels"
    assert report["promotion_recommendation"] is None
    off = report["variants"]["htf_trailing_off"]["metrics"]["development"]
    assert off["completed_positions"] == 1
    assert off["net_pnl"] == 3.0  # development result excludes the registered OOS entry window
    oos = report["variants"]["htf_trailing_off"]["metrics"]["locked_oos"]
    assert oos["completed_positions"] == 2  # P3 closes after the entry-window end but before maturity
    assert oos["net_pnl"] == -14.0
    assert report["variants"]["htf_trailing_off"]["metrics"]["locked_oos_censoring"]["closed_after_maturity_cut"] == 0
    assert report["on_minus_off_deltas"]["locked_oos"]["net_pnl"] == 0


def test_mismatched_context_is_rejected(tmp_path):
    path = _make_manifest(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["variants"][1]["observed_context"]["risk_percent"] = 0.7
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MatchedTrailingError, match="risk_percent"):
        compare_manifest(path)


def test_any_set_difference_beyond_the_trailing_master_toggle_is_rejected(tmp_path):
    path = _make_manifest(tmp_path, add_setting_difference=("htf_trailing_on", "InpRiskPercentPerTrade", "0.7"))
    with pytest.raises(MatchedTrailingError, match="only InpDynamicStopUseHTFReferenceLevels may differ"):
        compare_manifest(path)


def test_missing_weekly_or_monthly_reference_is_rejected(tmp_path):
    path = _make_manifest(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    on_path = tmp_path / payload["variants"][1]["input_preset"]
    on_path.write_text(on_path.read_text(encoding="utf-8").replace("InpDynamicStopUseWeeklyReference=true", "InpDynamicStopUseWeeklyReference=false"), encoding="utf-8")
    with pytest.raises(MatchedTrailingError, match="requires InpDynamicStopUseWeeklyReference=true"):
        compare_manifest(path)


def test_missing_cost_column_is_rejected(tmp_path):
    path = _make_manifest(tmp_path, omit_swap=True)
    with pytest.raises(MatchedTrailingError, match="explicitly export commission, swap, and fee"):
        compare_manifest(path)


def test_default_comparison_withholds_locked_oos_metrics(tmp_path):
    report = compare_manifest(_make_manifest(tmp_path))
    assert "locked_oos" not in report["variants"]["htf_trailing_off"]["metrics"]
    assert "development" in report["variants"]["htf_trailing_off"]["metrics"]
    assert report["locked_oos_status"] == "scored only by the one-shot gate"
