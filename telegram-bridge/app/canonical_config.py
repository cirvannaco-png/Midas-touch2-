"""Canonical JSON identity compatible with Medis Touch config hashing."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("configuration contains a non-finite float")
        return float(format(value, ".15g"))
    if hasattr(value, "value"):
        return _normalize(value.value)
    return value


def canonical_json(value: dict[str, Any]) -> str:
    """Return the source-compatible compact serialization used for hashing."""
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_hash(value: dict[str, Any]) -> str:
    """SHA-256 hash of source-compatible canonical configuration JSON."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
