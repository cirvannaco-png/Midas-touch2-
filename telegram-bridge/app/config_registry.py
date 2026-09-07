"""Immutable candidate-configuration identity and promotion lifecycle guards.

This module deliberately does not mutate EA configuration.  It records the
identity/evidence boundary that a candidate must cross before deployment.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass


LIFECYCLE = (
    "OPTIMIZED",
    "BACKTESTED",
    "VALIDATED",
    "QUARANTINE",
    "SHADOW",
    "CHALLENGER",
    "CHAMPION",
)

_TRANSITIONS = {
    "OPTIMIZED": {"BACKTESTED"},
    "BACKTESTED": {"VALIDATED"},
    "VALIDATED": {"QUARANTINE"},
    "QUARANTINE": {"SHADOW"},
    "SHADOW": {"CHALLENGER"},
    "CHALLENGER": {"CHAMPION"},
    "CHAMPION": set(),
}


def canonical_config(payload: Mapping[str, object]) -> str:
    """Return a deterministic JSON representation suitable for hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def configuration_hash(payload: Mapping[str, object]) -> str:
    """Return the SHA-256 identity of a complete candidate configuration."""
    return hashlib.sha256(canonical_config(payload).encode("utf-8")).hexdigest()


def validate_transition(current: str, target: str) -> None:
    """Fail closed unless *target* is the single permitted next lifecycle."""
    if current not in _TRANSITIONS:
        raise ValueError(f"unknown lifecycle status: {current}")
    if target not in LIFECYCLE:
        raise ValueError(f"unknown lifecycle status: {target}")
    if target not in _TRANSITIONS[current]:
        raise ValueError(f"illegal lifecycle transition: {current} -> {target}")


def assert_identity_unchanged(original: Mapping[str, object], replacement: Mapping[str, object]) -> None:
    """Reject edits to fields that define immutable configuration identity."""
    if canonical_config(original) != canonical_config(replacement):
        raise ValueError("immutable configuration identity cannot be overwritten; create a new candidate")


@dataclass(frozen=True)
class ConfigurationIdentity:
    """Canonical identity/provenance envelope for one candidate."""

    strategy: str
    instrument: str
    timeframe: str
    parameters: Mapping[str, object]
    data_version: str
    optimizer_version: str

    def payload(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "parameters": dict(self.parameters),
            "data_version": self.data_version,
            "optimizer_version": self.optimizer_version,
        }

    @property
    def config_hash(self) -> str:
        return configuration_hash(self.payload())
