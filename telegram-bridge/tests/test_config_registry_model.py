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
