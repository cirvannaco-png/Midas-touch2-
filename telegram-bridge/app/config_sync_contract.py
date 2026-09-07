"""Fail-closed contract for approved configuration delivery to an EA.

This module defines the protocol boundary only. It does not mutate trading
logic or decide which parameters should be optimized. A configuration may be
activated only when its immutable identity, hash, and expected deployment
metadata agree and an explicit EA acknowledgement is received.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.config_registry import ConfigurationIdentity


@dataclass(frozen=True)
class ConfigSyncEnvelope:
    """Immutable configuration envelope delivered to one EA instance."""

    config_hash: str
    strategy: str
    instrument: str
    timeframe: str
    parameters: Mapping[str, object]
    data_version: str
    optimizer_version: str
    lifecycle_status: str
    version: int

    def identity(self) -> ConfigurationIdentity:
        return ConfigurationIdentity(
            strategy=self.strategy,
            instrument=self.instrument,
            timeframe=self.timeframe,
            parameters=self.parameters,
            data_version=self.data_version,
            optimizer_version=self.optimizer_version,
        )


@dataclass(frozen=True)
class ConfigSyncDecision:
    action: str
    reasons: tuple[str, ...]


def validate_envelope(
    envelope: ConfigSyncEnvelope,
    *,
    expected_symbol: str,
    expected_timeframe: str,
    expected_strategy: str,
) -> ConfigSyncDecision:
    """Validate identity and deployment metadata without applying anything."""
    reasons: list[str] = []

    if envelope.version < 1:
        reasons.append("configuration version must be positive")
    if envelope.lifecycle_status not in {"SHADOW", "CHALLENGER", "CHAMPION"}:
        reasons.append("configuration is not deployable at its lifecycle status")
    if envelope.instrument != expected_symbol:
        reasons.append("instrument mismatch")
    if envelope.timeframe != expected_timeframe:
        reasons.append("timeframe mismatch")
    if envelope.strategy != expected_strategy:
        reasons.append("strategy mismatch")
    if not isinstance(envelope.parameters, Mapping):
        reasons.append("parameters must be a mapping")

    if not reasons:
        computed_hash = envelope.identity().config_hash
        if computed_hash != envelope.config_hash:
            reasons.append("configuration hash mismatch")

    if reasons:
        return ConfigSyncDecision("REJECT", tuple(reasons))
    return ConfigSyncDecision("READY", ("configuration identity and deployment metadata validated",))


def activation_decision(
    validation: ConfigSyncDecision,
    *,
    acknowledged_hash: str | None,
    expected_hash: str,
) -> ConfigSyncDecision:
    """Permit activation only after validation and an exact EA acknowledgement."""
    if validation.action != "READY":
        return ConfigSyncDecision("HOLD", ("configuration validation did not pass", *validation.reasons))
    if not acknowledged_hash:
        return ConfigSyncDecision("HOLD", ("EA acknowledgement is required before activation",))
    if acknowledged_hash != expected_hash:
        return ConfigSyncDecision("HOLD", ("EA acknowledgement hash mismatch",))
    return ConfigSyncDecision("ACTIVATE", ("validated configuration acknowledged by EA",))


def rollback_decision(*, active_hash: str, champion_hash: str, runtime_healthy: bool) -> ConfigSyncDecision:
    """Fail safe to the last known-good champion after runtime degradation."""
    if runtime_healthy:
        return ConfigSyncDecision("KEEP_ACTIVE", ("active configuration remains healthy",))
    if not champion_hash:
        return ConfigSyncDecision("HALT", ("runtime unhealthy and no champion configuration is available",))
    if active_hash == champion_hash:
        return ConfigSyncDecision("DEFENSIVE", ("champion is unhealthy; enter defensive/no-new-trades state",))
    return ConfigSyncDecision("ROLLBACK", ("runtime degradation requires rollback to champion",))


def envelope_from_mapping(payload: Mapping[str, Any]) -> ConfigSyncEnvelope:
    """Parse a transport mapping strictly enough to avoid silent defaults."""
    required = (
        "config_hash",
        "strategy",
        "instrument",
        "timeframe",
        "parameters",
        "data_version",
        "optimizer_version",
        "lifecycle_status",
        "version",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"missing configuration fields: {', '.join(missing)}")
    return ConfigSyncEnvelope(
        config_hash=str(payload["config_hash"]),
        strategy=str(payload["strategy"]),
        instrument=str(payload["instrument"]),
        timeframe=str(payload["timeframe"]),
        parameters=payload["parameters"],
        data_version=str(payload["data_version"]),
        optimizer_version=str(payload["optimizer_version"]),
        lifecycle_status=str(payload["lifecycle_status"]),
        version=int(payload["version"]),
    )
