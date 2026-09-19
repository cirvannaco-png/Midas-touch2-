"""Tests for walk-forward windowing, statistical verdicts, and CSV ingestion."""
import csv
from datetime import datetime, timedelta, timezone

import pytest

from walk_forward import compute_rolling_walk_forward_report, compute_walk_forward_report, ingest_tester_csv, split_train_holdout

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_split_train_holdout_boundary_placement(make_outcome):
    rows = [
        make_outcome(received_at=NOW - timedelta(weeks=5)),
        make_outcome(received_at=NOW - timedelta(weeks=3)),
        make_outcome(received_at=NOW - timedelta(days=3)),
        make_outcome(received_at=NOW - timedelta(hours=1)),
    ]
    train, holdout = split_train_holdout(rows, reference_weeks=4, holdout_weeks=1, now=NOW)
    assert len(train) == 1
    assert len(holdout) == 2


def test_split_train_holdout_drops_rows_with_no_received_at(make_outcome):
    rows = [make_outcome(received_at=None), make_outcome(received_at=NOW - timedelta(days=1))]
    train, holdout = split_train_holdout(rows, reference_weeks=4, holdout_weeks=1, now=NOW)
    assert (len(train) + len(holdout)) == 1


def test_split_train_holdout_rejects_invalid_window():
    with pytest.raises(ValueError):
        split_train_holdout([], reference_weeks=1, holdout_weeks=1)


def test_walk_forward_verdict_insufficient_data_with_no_resolved_rows(make_outcome):
    rows = [make_outcome(weight_version="v2.11-baseline", outcome="no_fill", received_at=NOW - timedelta(days=1))]
    report = compute_walk_forward_report(rows, "v2.11-baseline", reference_weeks=4, holdout_weeks=1)
    assert report["verdict"] == "insufficient_data"
    assert report["overlap"] is None


def test_walk_forward_verdict_consistent_when_train_and_holdout_agree(make_outcome):
    wv = "v2.11-baseline"
    rows = []
    for i in range(40):
        rows.append(make_outcome(weight_version=wv, outcome=("win" if i % 2 == 0 else "loss"), realized_r=(1.0 if i % 2 == 0 else -1.0), received_at=NOW - timedelta(weeks=2, days=i % 5)))
    for i in range(40):
        rows.append(make_outcome(weight_version=wv, outcome=("win" if i % 2 == 0 else "loss"), realized_r=(1.0 if i % 2 == 0 else -1.0), received_at=NOW - timedelta(hours=i)))
    report = compute_walk_forward_report(rows, wv, reference_weeks=4, holdout_weeks=1)
    assert report["verdict"] == "consistent"
    assert report["overlap"] is True


def test_walk_forward_verdict_diverged_when_holdout_regresses(make_outcome):
    wv = "v2.11-baseline"
    rows = []
    for i in range(60):
        rows.append(make_outcome(weight_version=wv, outcome=("win" if i < 50 else "loss"), realized_r=(1.0 if i < 50 else -1.0), received_at=NOW - timedelta(weeks=2, hours=i)))
    for i in range(60):
        rows.append(make_outcome(weight_version=wv, outcome=("win" if i < 10 else "loss"), realized_r=(1.0 if i < 10 else -1.0), received_at=NOW - timedelta(hours=i)))
    report = compute_walk_forward_report(rows, wv, reference_weeks=4, holdout_weeks=1)
    assert report["verdict"] == "diverged"
    assert report["overlap"] is False


def test_walk_forward_filters_to_requested_weight_version_only(make_outcome):
    rows = [
        make_outcome(weight_version="v2.11-baseline", outcome="win", realized_r=1.0, received_at=NOW - timedelta(hours=1)),
        make_outcome(weight_version="v2.10-old", outcome="win", realized_r=1.0, received_at=NOW - timedelta(hours=1)),
    ]
    report = compute_walk_forward_report(rows, "v2.11-baseline", reference_weeks=4, holdout_weeks=1)
    assert report["holdout"]["coverage"]["total_signals"] == 1


def test_ingest_tester_csv_strictly_parses_known_columns(tmp_path):
    path = tmp_path / "tester.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["decision_id", "outcome", "realized_r", "regime", "unknown"])
        writer.writeheader()
        writer.writerow({"decision_id": "42", "outcome": "WIN", "realized_r": "1.25", "regime": "TRENDING", "unknown": "kept"})
    rows = ingest_tester_csv(str(path))
    assert rows[0]["signal_id"] == "42"
    assert rows[0]["outcome"] == "win"
    assert rows[0]["realized_r"] == 1.25
    assert rows[0]["raw"]["unknown"] == "kept"


def test_ingest_tester_csv_rejects_ambiguous_schema(tmp_path):
    path = tmp_path / "tester.csv"
    path.write_text("foo,bar\n1,WIN\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required"):
        ingest_tester_csv(str(path))


def test_ingest_tester_csv_rejects_unknown_outcome(tmp_path):
    path = tmp_path / "tester.csv"
    path.write_text("signal_id,outcome\n42,pending\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported outcome"):
        ingest_tester_csv(str(path))


def test_rolling_walk_forward_uses_signal_time_and_keeps_temporal_order(make_outcome):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(70):
        rows.append(make_outcome(
            symbol="EURUSD", strategy="SMC", weight_version="v2.11-baseline",
            received_at=base + timedelta(days=i + 2), signal_time=base + timedelta(days=i),
            outcome=("win" if i % 2 == 0 else "loss"), realized_r=(1.0 if i % 2 == 0 else -1.0),
        ))
    report = compute_rolling_walk_forward_report(
        rows, "v2.11-baseline", train_weeks=4, holdout_weeks=1,
        step_weeks=1, folds=3, symbol="EURUSD", strategy="SMC"
    )
    assert len(report["folds"]) == 3
    for fold in report["folds"]:
        assert fold["train_max_signal_time"] < fold["holdout_min_signal_time"]
    assert report["asset_class"] == "fx"
