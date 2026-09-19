"""Eligibility firewall for locked out-of-sample research.

The firewall validates lineage/provenance before any OOS statistic is computed.
It is deliberately conservative: missing evidence produces rejection rather
than inferred defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

from instrument_taxonomy import classify_symbol
from decision_fingerprint import fingerprint_canonical


class OOSPurityError(ValueError):
    pass


REQUIRED_PROVENANCE = (
    "signal_time",
    "decision_time",
    "data_received_time",
    "strategy_version",
    "model_version",
    "weight_version",
    "calibration_version",
    "feature_schema_version",
    "environment_schema_version",
    "decision_fingerprint",
    "canonical_decision",
    "parity_status",
    "strategy",
    "symbol",
    "asset_class",
)


def _dt(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise OOSPurityError(f"missing or invalid {field}")


def validate_records(
    records: Sequence[Mapping[str, object]],
    *,
    evaluation_now: datetime | None = None,
    allowed_sources: set[str] | None = None,
) -> None:
    if not records:
        raise OOSPurityError("empty dataset")
    now = evaluation_now or datetime.now(timezone.utc)
    sources: set[str] = set()
    seen_decisions: set[object] = set()
    seen_signals: set[object] = set()

    for idx, row in enumerate(records):
        for field in REQUIRED_PROVENANCE:
            if row.get(field) in (None, ""):
                raise OOSPurityError(f"row {idx}: missing {field}")
        decision_id = row.get("decision_id", row.get("signal_id"))
        signal_id = row.get("signal_id")
        if decision_id in seen_decisions:
            raise OOSPurityError(f"row {idx}: duplicate decision_id={decision_id}")
        if signal_id in seen_signals:
            raise OOSPurityError(f"row {idx}: duplicate signal_id={signal_id}")
        seen_decisions.add(decision_id)
        seen_signals.add(signal_id)

        signal_time = _dt(row["signal_time"], "signal_time")
        decision_time = _dt(row["decision_time"], "decision_time")
        received = _dt(row["data_received_time"], "data_received_time")
        if signal_time > decision_time or decision_time > received:
            raise OOSPurityError(f"row {idx}: invalid temporal order")
        for name in ("execution_time", "outcome_time"):
            if row.get(name) not in (None, "") and _dt(row[name], name) > now:
                raise OOSPurityError(f"row {idx}: future timestamp in {name}")

        if signal_time > now or decision_time > now or received > now:
            raise OOSPurityError(f"row {idx}: future provenance timestamp")

        source = str(row.get("source_type", "")).lower()
        if source:
            sources.add(source)
        if str(row.get("parity_status", "")).upper() != "PARITY_OK":
            raise OOSPurityError(f"row {idx}: decision parity status is not PARITY_OK")
        if row.get("original_decision_fingerprint") not in (None, "", row["decision_fingerprint"]):
            raise OOSPurityError(f"row {idx}: altered historical decision")
        if fingerprint_canonical(str(row["canonical_decision"])) != str(row["decision_fingerprint"]).upper():
            raise OOSPurityError(f"row {idx}: decision fingerprint does not match canonical decision")

        expected_class = classify_symbol(str(row["symbol"]))
        if expected_class != "other" and row["asset_class"] != expected_class:
            raise OOSPurityError(f"row {idx}: instrument classification mismatch")

        if bool(row.get("filled")):
            for field in ("commission_cost", "spread_cost", "slippage_cost", "execution_time", "outcome_time"):
                if row.get(field) in (None, ""):
                    raise OOSPurityError(f"row {idx}: incomplete execution provenance: {field}")

    if allowed_sources is not None and not sources.issubset(allowed_sources):
        raise OOSPurityError(f"disallowed source types: {sorted(sources - allowed_sources)}")
    if len(sources) > 1:
        raise OOSPurityError("mixed synthetic/live/tester sources")


@dataclass(frozen=True)
class TemporalSplit:
    train: Sequence[Mapping[str, object]]
    validation: Sequence[Mapping[str, object]]
    locked_oos: Sequence[Mapping[str, object]]


def validate_temporal_split(split: TemporalSplit) -> None:
    if not split.train or not split.validation or not split.locked_oos:
        raise OOSPurityError("train, validation, and locked OOS must all be populated")

    train_max = max(_dt(r["signal_time"], "signal_time") for r in split.train)
    validation_min = min(_dt(r["signal_time"], "signal_time") for r in split.validation)
    validation_max = max(_dt(r["signal_time"], "signal_time") for r in split.validation)
    oos_min = min(_dt(r["signal_time"], "signal_time") for r in split.locked_oos)
    if not train_max < validation_min:
        raise OOSPurityError("training_max_signal_time must be < validation_min_signal_time")
    if not validation_max < oos_min:
        raise OOSPurityError("validation_max_signal_time must be < holdout_min_signal_time")
