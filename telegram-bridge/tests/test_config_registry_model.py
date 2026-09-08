import pytest

from app.config_registry import ConfigurationIdentity
from app.config_registry_model import ConfigurationRegistry


def test_registry_model_materializes_identity_and_defaults():
    identity = ConfigurationIdentity(
        strategy="momentum_breakout",
        instrument="XAUUSD",
        timeframe="M15",
        parameters={"atr_period": 14, "risk_percent": 0.5},
        data_version="market-data-v1",
        optimizer_version="optimizer-v1",
    )

    row = ConfigurationRegistry.from_identity(identity)

    assert row.config_hash == identity.config_hash
    assert row.strategy == identity.strategy
    assert row.instrument == identity.instrument
    assert row.timeframe == identity.timeframe
    assert row.parameters == dict(identity.parameters)
    assert row.lifecycle_status == "OPTIMIZED"
    assert row.risk_metrics == {}


def test_registry_model_cannot_skip_lifecycle_evidence():
    identity = ConfigurationIdentity(
        strategy="momentum_breakout",
        instrument="XAUUSD",
        timeframe="M15",
        parameters={"atr_period": 14},
        data_version="market-data-v1",
        optimizer_version="optimizer-v1",
    )
    row = ConfigurationRegistry.from_identity(identity)

    row.transition_to("BACKTESTED")
    row.transition_to("VALIDATED")
    row.transition_to("QUARANTINE")

    with pytest.raises(ValueError, match="illegal lifecycle transition"):
        row.transition_to("CHAMPION")

    assert row.lifecycle_status == "QUARANTINE"


def test_registry_identity_fields_are_immutable():
    identity = ConfigurationIdentity(
        strategy="momentum_breakout",
        instrument="XAUUSD",
        timeframe="M15",
        parameters={"atr_period": 14},
        data_version="market-data-v1",
        optimizer_version="optimizer-v1",
    )
    row = ConfigurationRegistry.from_identity(identity)

    row.strategy = "mean_reversion"

    with pytest.raises(ValueError, match="configuration identity fields are immutable"):
        from sqlalchemy import event
        from sqlalchemy.orm import configure_mappers

        configure_mappers()
        event.registry = None
        # Trigger the mapper's before_update listener without requiring a DB.
        from sqlalchemy import inspect

        assert inspect(row).attrs.strategy.history.has_changes()
        for listener in row.__mapper__.dispatch.before_update:
            listener(row.__mapper__, None, row)
