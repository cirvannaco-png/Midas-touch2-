import pytest

from app.config_registry import (
    ConfigurationIdentity,
    LIFECYCLE,
    assert_identity_unchanged,
    canonical_config,
    configuration_hash,
    validate_transition,
)


def _identity() -> ConfigurationIdentity:
    return ConfigurationIdentity(
        strategy="momentum_breakout",
        instrument="XAUUSD",
        timeframe="M15",
        parameters={"atr_period": 14, "risk_percent": 0.5},
        data_version="market-data-v1",
        optimizer_version="optimizer-v1",
    )


def test_canonicalization_is_order_independent() -> None:
    assert canonical_config({"b": 2, "a": 1}) == canonical_config({"a": 1, "b": 2})
    assert configuration_hash({"b": 2, "a": 1}) == configuration_hash({"a": 1, "b": 2})


def test_identity_hash_changes_when_parameter_changes() -> None:
    first = _identity()
    changed = ConfigurationIdentity(
        strategy=first.strategy,
        instrument=first.instrument,
        timeframe=first.timeframe,
        parameters={"atr_period": 15, "risk_percent": 0.5},
        data_version=first.data_version,
        optimizer_version=first.optimizer_version,
    )
    assert first.config_hash != changed.config_hash


def test_identity_hash_changes_when_provenance_changes() -> None:
    first = _identity()
    changed = ConfigurationIdentity(
        strategy=first.strategy,
        instrument=first.instrument,
        timeframe=first.timeframe,
        parameters=first.parameters,
        data_version="market-data-v2",
        optimizer_version=first.optimizer_version,
    )
    assert first.config_hash != changed.config_hash


def test_immutable_identity_rejects_overwrite() -> None:
    original = _identity().payload()
    replacement = dict(original)
    replacement["parameters"] = {"atr_period": 15, "risk_percent": 0.5}
    with pytest.raises(ValueError, match="cannot be overwritten"):
        assert_identity_unchanged(original, replacement)


def test_unchanged_identity_is_accepted() -> None:
    original = _identity().payload()
    assert_identity_unchanged(original, dict(original))


def test_lifecycle_is_strict_and_fail_closed() -> None:
    assert LIFECYCLE == (
        "OPTIMIZED",
        "BACKTESTED",
        "VALIDATED",
        "QUARANTINE",
        "SHADOW",
        "CHALLENGER",
        "CHAMPION",
    )
    for current, target in zip(LIFECYCLE, LIFECYCLE[1:]):
        validate_transition(current, target)

    with pytest.raises(ValueError, match="illegal lifecycle transition"):
        validate_transition("OPTIMIZED", "CHAMPION")
    with pytest.raises(ValueError, match="illegal lifecycle transition"):
        validate_transition("CHAMPION", "SHADOW")
    with pytest.raises(ValueError, match="unknown lifecycle status"):
        validate_transition("UNKNOWN", "BACKTESTED")
