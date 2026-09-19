"""Build a signed-by-hash research/decision certification artifact."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def build_certificate(
    *,
    build: Mapping[str, Any],
    ea: Mapping[str, Any],
    decision_schema: Mapping[str, Any],
    dataset: Mapping[str, Any],
    training: Mapping[str, Any],
    validation: Mapping[str, Any],
    oos: Mapping[str, Any],
    trades: Mapping[str, Any],
    costs: Mapping[str, Any],
    metrics: Mapping[str, Any],
    gates: Mapping[str, Any],
) -> dict[str, Any]:
    artifact = {
        "artifact_type": "MIDAS_TOUCH_DECISION_RESEARCH_CERTIFICATE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build": deepcopy(dict(build)),
        "ea": deepcopy(dict(ea)),
        "decision_schema": deepcopy(dict(decision_schema)),
        "dataset": deepcopy(dict(dataset)),
        "training": deepcopy(dict(training)),
        "validation": deepcopy(dict(validation)),
        "oos": deepcopy(dict(oos)),
        "trades": deepcopy(dict(trades)),
        "costs": deepcopy(dict(costs)),
        "metrics": deepcopy(dict(metrics)),
        "gates": deepcopy(dict(gates)),
    }
    required = ("parity", "temporal_isolation", "replay_determinism", "data_provenance")
    values = [str(gates.get(k, "")).upper() for k in required]
    artifact["certification"] = (
        "PASS" if all(v == "PASS" for v in values) and str(oos.get("status", "")).upper() == "PASS"
        else "FAIL" if any(v == "FAIL" for v in values + [str(oos.get("status", "")).upper()])
        else "INSUFFICIENT_EVIDENCE"
    )
    unsigned = dict(artifact)
    unsigned.pop("certificate_hash", None)
    artifact["certificate_hash"] = hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest().upper()
    return artifact
