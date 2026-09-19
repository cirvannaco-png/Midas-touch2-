"""Canonical decision envelope and deterministic SHA-256 fingerprints.

The canonical serialization is intentionally boring: fixed field order, explicit
names, ASCII-safe values, and stable decimal formatting. The same contract can
be implemented by the EA and the backend so the fingerprint is portable across
the execution boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from typing import Any, Mapping

SCHEMA_VERSION = "decision-v1"
CANONICAL_FIELDS = (
    "schema_version",
    "decision_id",
    "symbol",
    "direction",
    "entry",
    "invalidation",
    "sl",
    "tp1",
    "tp2",
    "final_tp",
    "confidence",
    "action",
    "reduce_risk",
    "spread_points",
    "regime",
    "strategy",
    "session",
    "weight_version",
    "strategy_version",
    "model_version",
    "calibration_version",
    "feature_schema_version",
    "environment_schema_version",
    "environment_key",
)

PRICE_FIELDS = {"entry", "invalidation", "sl", "tp1", "tp2", "final_tp", "spread_points"}


def _decimal(value: Any, places: int = 8) -> str:
    if value is None:
        return "null"
    quant = Decimal("1").scaleb(-places)
    return format(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP), "f")


def _scalar(name: str, value: Any) -> str:
    if value is None:
        return "null"
    if name in PRICE_FIELDS:
        return _decimal(value, 8)
    if name == "confidence":
        return _decimal(value, 4)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def canonical_fields(payload: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in CANONICAL_FIELDS:
        value = payload.get(name)
        if name == "schema_version" and value in (None, ""):
            value = SCHEMA_VERSION
        out[name] = _scalar(name, value)
    return out


def canonical_serialize(payload: Mapping[str, Any]) -> str:
    values = canonical_fields(payload)
    return "|".join(f"{name}={values[name]}" for name in CANONICAL_FIELDS)


def fingerprint_canonical(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()


def fingerprint(payload: Mapping[str, Any]) -> str:
    return fingerprint_canonical(canonical_serialize(payload))


@dataclass(frozen=True)
class DecisionEnvelope:
    payload: Mapping[str, Any]

    @property
    def canonical(self) -> str:
        return canonical_serialize(self.payload)

    @property
    def decision_fingerprint(self) -> str:
        return fingerprint(self.payload)

    def as_record(self) -> dict[str, Any]:
        record = dict(self.payload)
        record["schema_version"] = record.get("schema_version") or SCHEMA_VERSION
        record["decision_fingerprint"] = self.decision_fingerprint
        record["canonical_decision"] = self.canonical
        return record
