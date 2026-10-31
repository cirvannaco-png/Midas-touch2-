import pytest
import hashlib
from datetime import datetime, timedelta, timezone

from tools.oos_firewall import (
    OOSPurityError,
    TemporalSplit,
    optimizer_development_view,
    validate_records,
    validate_temporal_split,
)


def row(i, when):
    return {
        "decision_id": i,
        "signal_id": f"s{i}",
        "signal_time": when,
        "decision_time": when + timedelta(seconds=1),
        "data_received_time": when + timedelta(seconds=2),
        "execution_time": when + timedelta(seconds=3),
        "outcome_time": when + timedelta(seconds=60),
        "strategy_version": "sv1",
        "model_version": "mv1",
        "weight_version": "wv1",
        "calibration_version": "cv1",
        "feature_schema_version": "fv1",
        "environment_schema_version": "ev1",
        "decision_fingerprint": hashlib.sha256(b"test-canonical").hexdigest().upper(),
        "canonical_decision": "test-canonical",
        "parity_status": "PARITY_OK",
        "strategy": "SMC",
        "symbol": "EURUSD",
        "asset_class": "fx",
        "filled": True,
        "commission_cost": 1.0,
        "spread_cost": 1.0,
        "slippage_cost": 1.0,
        "source_type": "tester",
    }


def test_firewall_accepts_clean_dataset():
    now = datetime.now(timezone.utc)
    validate_records([row(1, now - timedelta(days=2))], evaluation_now=now)


def test_firewall_rejects_duplicate_decision():
    now = datetime.now(timezone.utc)
    with pytest.raises(OOSPurityError):
        validate_records([row(1, now - timedelta(days=2)), row(1, now - timedelta(days=1))], evaluation_now=now)


def test_temporal_split_is_strictly_ordered():
    now = datetime.now(timezone.utc)
    train = [row(1, now - timedelta(days=5))]
    validation = [row(2, now - timedelta(days=4))]
    oos = [row(3, now - timedelta(days=2))]
    validate_temporal_split(TemporalSplit(train, validation, oos))


def test_optimizer_development_view_excludes_locked_oos_by_rejection():
    train = {"partition": "train", "signal_time": "2026-01-01T00:00:00Z", "id": "t1"}
    validation = {"partition": "validation", "signal_time": "2026-01-02T00:00:00Z", "id": "v1"}
    view = optimizer_development_view([train, validation])
    assert [row["id"] for row in view] == ["t1", "v1"]
    assert all(row["partition"] in {"train", "validation"} for row in view)


def test_optimizer_rejects_locked_oos_instead_of_silently_filtering_it():
    records = [
        {"partition": "train", "id": "train"},
        {"partition": "locked_oos", "id": "holdout"},
    ]
    with pytest.raises(OOSPurityError, match="locked OOS records are prohibited"):
        optimizer_development_view(records)


def test_optimizer_rejects_unlabelled_or_unknown_partition():
    with pytest.raises(OOSPurityError, match="explicitly tagged"):
        optimizer_development_view([{"id": "unknown"}])


def test_temporal_split_rejects_train_validation_and_holdout_overlap():
    now = datetime.now(timezone.utc)
    train = [row(1, now - timedelta(days=5)), row(2, now - timedelta(days=4))]
    validation = [row(3, now - timedelta(days=4))]
    holdout = [row(4, now - timedelta(days=2))]
    with pytest.raises(OOSPurityError, match="training_max_signal_time"):
        validate_temporal_split(TemporalSplit(train, validation, holdout))


def test_temporal_split_rejects_validation_holdout_overlap():
    now = datetime.now(timezone.utc)
    train = [row(1, now - timedelta(days=6))]
    validation = [row(2, now - timedelta(days=3)), row(3, now - timedelta(days=2))]
    holdout = [row(4, now - timedelta(days=2))]
    with pytest.raises(OOSPurityError, match="validation_max_signal_time"):
        validate_temporal_split(TemporalSplit(train, validation, holdout))
