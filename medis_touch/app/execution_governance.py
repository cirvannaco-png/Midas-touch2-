"""Canonical execution configuration identity and promotion checks."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionConfig:
    version: str
    policy: str
    max_order_notional: float
    max_spread_bps: float
    max_participation: float
    allowed_venues: tuple[str, ...]
    model_hash: str

    def canonical(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "policy": self.policy,
            "max_order_notional": self.max_order_notional,
            "max_spread_bps": self.max_spread_bps,
            "max_participation": self.max_participation,
            "allowed_venues": sorted(self.allowed_venues),
            "model_hash": self.model_hash,
        }

    @property
    def config_hash(self) -> str:
        payload = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def promotion_allowed(*, challenger: ExecutionConfig, approved_hash: str | None, evidence_passed: bool) -> bool:
    """Promotion is allowed only when evidence passes and the exact hash is approved."""
    return evidence_passed and approved_hash == challenger.config_hash


def attach_identity(metadata: dict[str, Any], config: ExecutionConfig) -> dict[str, Any]:
    return {**metadata, "execution_config_hash": config.config_hash, "execution_model_hash": config.model_hash}
