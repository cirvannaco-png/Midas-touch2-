from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.config_sync import _verify_registry_hash
from app.config_registry import ConfigurationIdentity
from app.config_sync_state_model import ConfigSyncState


def make_registry(**overrides):
    values = {
        "strategy": "SMC",
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "parameters": {"confidence_threshold": 90},
        "data_version": "data-2026-09-01",
        "optimizer_version": "optimizer-1",
    }
    values.update(overrides)
    values["config_hash"] = ConfigurationIdentity(**values).config_hash
    return SimpleNamespace(**values)


def test_transport_rejects_tampered_registry_hash():
    registry = make_registry(config_hash="0" * 64)
    with pytest.raises(HTTPException, match="identity/hash mismatch"):
        _verify_registry_hash(registry)


def test_transport_accepts_canonical_registry_identity():
    _verify_registry_hash(make_registry())


def test_sync_state_has_durable_activation_fields():
    columns = ConfigSyncState.__table__.columns
    assert {"symbol", "active_config_hash", "acknowledged_config_hash", "state", "last_ack_at", "last_seen_at"} <= set(columns.keys())
