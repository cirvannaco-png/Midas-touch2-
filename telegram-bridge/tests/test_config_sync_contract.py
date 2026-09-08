import pytest

from app.config_registry import ConfigurationIdentity
from app.config_sync_contract import (
    ConfigSyncEnvelope,
    activation_decision,
    envelope_from_mapping,
    rollback_decision,
    validate_envelope,
)


def make_envelope(**overrides):
    values = {
        "strategy": "SMC",
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "parameters": {"confidence_threshold": 90},
        "data_version": "data-2026-09-01",
        "optimizer_version": "optimizer-1",
        "lifecycle_status": "CHAMPION",
        "version": 1,
    }
    explicit_hash = overrides.pop("config_hash", None)
    values.update(overrides)
    values["config_hash"] = (
        explicit_hash
        if explicit_hash is not None
        else ConfigurationIdentity(
            strategy=values["strategy"],
            instrument=values["instrument"],
            timeframe=values["timeframe"],
            parameters=values["parameters"],
            data_version=values["data_version"],
            optimizer_version=values["optimizer_version"],
        ).config_hash
    )
    return ConfigSyncEnvelope(**values)


def test_matching_champion_identity_is_ready():
    envelope = make_envelope()
    decision = validate_envelope(
        envelope,
        expected_symbol="XAUUSD",
        expected_timeframe="M15",
        expected_strategy="SMC",
    )
    assert decision.action == "READY"


def test_challenger_cannot_cross_activation_boundary():
    envelope = make_envelope(lifecycle_status="CHALLENGER")
    decision = validate_envelope(
        envelope,
        expected_symbol="XAUUSD",
        expected_timeframe="M15",
        expected_strategy="SMC",
    )
    assert decision.action == "REJECT"
    assert "not a champion" in decision.reasons[0]


def test_unsupported_protocol_version_rejects():
    envelope = make_envelope(version=2)
    decision = validate_envelope(
        envelope,
        expected_symbol="XAUUSD",
        expected_timeframe="M15",
        expected_strategy="SMC",
    )
    assert decision.action == "REJECT"
    assert "unsupported configuration protocol version" in decision.reasons


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("instrument", "EURUSD"),
        ("timeframe", "H1"),
        ("strategy", "MOMENTUM_BREAKOUT"),
    ],
)
def test_deployment_metadata_mismatch_rejects(field, expected):
    envelope = make_envelope()
    decision = validate_envelope(
        envelope,
        expected_symbol=expected if field == "instrument" else "XAUUSD",
        expected_timeframe=expected if field == "timeframe" else "M15",
        expected_strategy=expected if field == "strategy" else "SMC",
    )
    assert decision.action == "REJECT"
    assert any("mismatch" in reason for reason in decision.reasons)


def test_hash_tampering_rejects():
    envelope = make_envelope(config_hash="0" * 64)
    decision = validate_envelope(
        envelope,
        expected_symbol="XAUUSD",
        expected_timeframe="M15",
        expected_strategy="SMC",
    )
    assert decision.action == "REJECT"
    assert "configuration hash mismatch" in decision.reasons


def test_activation_requires_exact_acknowledgement():
    envelope = make_envelope()
    validation = validate_envelope(
        envelope,
        expected_symbol="XAUUSD",
        expected_timeframe="M15",
        expected_strategy="SMC",
    )
    assert activation_decision(validation, acknowledged_hash=None, expected_hash=envelope.config_hash).action == "HOLD"
    assert activation_decision(
        validation, acknowledged_hash="1" * 64, expected_hash=envelope.config_hash
    ).action == "HOLD"
    assert activation_decision(
        validation, acknowledged_hash=envelope.config_hash, expected_hash=envelope.config_hash
    ).action == "ACTIVATE"


def test_invalid_validation_cannot_activate_even_with_ack():
    validation = validate_envelope(
        make_envelope(config_hash="0" * 64),
        expected_symbol="XAUUSD",
        expected_timeframe="M15",
        expected_strategy="SMC",
    )
    assert activation_decision(
        validation, acknowledged_hash="0" * 64, expected_hash="0" * 64
    ).action == "HOLD"


def test_unhealthy_challenger_rolls_back_to_champion():
    decision = rollback_decision(
        active_hash="a" * 64,
        champion_hash="b" * 64,
        runtime_healthy=False,
    )
    assert decision.action == "ROLLBACK"


def test_unhealthy_champion_enters_defensive_state():
    decision = rollback_decision(
        active_hash="a" * 64,
        champion_hash="a" * 64,
        runtime_healthy=False,
    )
    assert decision.action == "DEFENSIVE"


def test_no_champion_halts_unhealthy_runtime():
    decision = rollback_decision(
        active_hash="a" * 64,
        champion_hash="",
        runtime_healthy=False,
    )
    assert decision.action == "HALT"


def test_no_champion_does_not_approve_healthy_runtime():
    decision = rollback_decision(
        active_hash="a" * 64,
        champion_hash="",
        runtime_healthy=True,
    )
    assert decision.action != "ROLLBACK"


def test_mapping_parser_rejects_missing_identity_fields():
    with pytest.raises(ValueError, match="missing configuration fields"):
        envelope_from_mapping({"config_hash": "a" * 64})
