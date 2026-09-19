import pytest
import hashlib
from datetime import datetime, timedelta, timezone

from tools.oos_firewall import OOSPurityError, TemporalSplit, validate_records, validate_temporal_split


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
