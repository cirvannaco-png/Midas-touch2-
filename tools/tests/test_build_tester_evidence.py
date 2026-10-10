import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from build_tester_evidence import BuildEvidenceError, build_evidence


BASE = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _timestamp(day):
    return (BASE + timedelta(days=day)).isoformat()


def _write_outcomes(path, days):
    fields = [
        "SignalID", "Symbol", "EntryTF", "Direction", "Outcome", "Filled",
        "SameBarSLTPCollision", "RealizedR", "Commission", "SpreadCost", "SlippageCost",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, day in enumerate(days):
            stamp = int((BASE + timedelta(days=day)).timestamp())
            is_win = index % 4 != 0
            writer.writerow({
                "SignalID": f"XAUUSD_BUY_{stamp}",
                "Symbol": "XAUUSD",
                "EntryTF": "PERIOD_M15",
                "Direction": "BUY",
                "Outcome": "resolved",
                "Filled": "Yes",
                "SameBarSLTPCollision": "No",
                "RealizedR": "0.50" if is_win else "-0.50",
                "Commission": "0.07",
                "SpreadCost": "0.03",
                "SlippageCost": "0.02",
            })


def _manifest(tmp_path, *, include_embargo_trade=False):
    days = [*range(0, 51), *([55] if include_embargo_trade else []), *range(60, 90)]
    csv_path = tmp_path / "outcomes.csv"
    _write_outcomes(csv_path, days)
    report_path = tmp_path / "tester-report.html"
    report_path.write_text("<html>fixture report</html>", encoding="utf-8")
    dataset_path = tmp_path / "market-data.bin"
    dataset_path.write_bytes(b"fixture market dataset bytes")
    data_sha = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    manifest = {
        "strategy": "MidasTouchIntegrated",
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "parameters": {"min_confidence": 60},
        "data_version": "xauusd-m15-fixture-data-v1",
        "optimizer_version": "tester-normalizer-test-v1",
        "dataset_sha256": data_sha,
        "dataset_path": "market-data.bin",
        "report_path": "tester-report.html",
        "candidate_csv": "outcomes.csv",
        "run_id": "normalizer-fixture-run",
        "signal_id_epoch_basis": "unix_utc",
        "provenance": {
            "ea_source_commit": "c" * 40,
            "ea_build": "MidasTouch-test-build",
            "terminal_build": "MT5-test-terminal",
            "data_vendor": "fixture-only",
            "period_start": _timestamp(0),
            "period_end": _timestamp(90),
            "locked_oos_start": _timestamp(60),
            "locked_oos_end": _timestamp(90),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "spread_model": "fixed-spread",
            "spread_points": 20,
            "commission_per_lot": 7,
            "slippage_points": 2,
            "fill_policy": "FILL_CONSERVATIVE",
        },
        "folds": [
            {
                "fold_id": 1,
                "train_start": _timestamp(0),
                "train_end": _timestamp(20),
                "validation_start": _timestamp(20),
                "validation_end": _timestamp(30),
            },
            {
                "fold_id": 2,
                "train_start": _timestamp(0),
                "train_end": _timestamp(30),
                "validation_start": _timestamp(30),
                "validation_end": _timestamp(40),
            },
            {
                "fold_id": 3,
                "train_start": _timestamp(0),
                "train_end": _timestamp(40),
                "validation_start": _timestamp(40),
                "validation_end": _timestamp(51),
            },
        ],
        "excluded_windows": [
            {"start": _timestamp(51), "end": _timestamp(60)},
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_normalizer_builds_chronological_evidence_bundle(tmp_path):
    manifest_path = _manifest(tmp_path)
    payload, summary = build_evidence(manifest_path)

    assert payload["provenance"]["source"] == "MT5_STRATEGY_TESTER"
    assert len(payload["provenance"]["report_sha256"]) == 64
    assert len(payload["provenance"]["outcome_csv_sha256"]) == 64
    assert payload["timeframe"] == "M15"
    assert len(payload["trades"]) > 100
    assert sum(row["partition"] == "locked_oos" for row in payload["trades"]) == 30
    assert {row["fold_id"] for row in payload["trades"] if row["partition"] == "validation"} == {1, 2, 3}
    assert summary["fold_count"] == 3
    assert summary["dataset_digest_status"] == "verified_from_dataset_file"
    assert summary["excluded_warmup_or_embargo_rows"] == 0
    assert summary["destination_file_not_sent"] is True
    assert "feature_importance" in summary["evidence_gaps_to_check"]


def test_normalizer_requires_explicit_signal_id_time_basis(tmp_path):
    manifest_path = _manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data.pop("signal_id_epoch_basis")
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BuildEvidenceError, match="signal_id_epoch_basis"):
        build_evidence(manifest_path)


def test_normalizer_rejects_unassigned_rows_without_declared_exclusion(tmp_path):
    manifest_path = _manifest(tmp_path, include_embargo_trade=True)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["excluded_windows"] = []
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BuildEvidenceError, match="not assigned to a declared"):
        build_evidence(manifest_path)


def test_normalizer_rejects_fold_leakage_in_manifest(tmp_path):
    manifest_path = _manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["folds"][0]["validation_start"] = _timestamp(19)
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BuildEvidenceError, match="ordered, non-overlapping"):
        build_evidence(manifest_path)
