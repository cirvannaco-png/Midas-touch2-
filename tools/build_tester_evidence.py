"""Normalize genuine Midas Touch OutcomeTracker CSV plus a split/evidence manifest.

The manifest must define all train/validation/OOS windows and any explicitly
excluded warm-up/embargo windows. Timestamps are derived from SignalID's epoch
suffix under an explicitly selected time-basis rule; no date format is guessed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
REQUIRED_CSV_COLUMNS = {
    "signalid",
    "symbol",
    "entrytf",
    "direction",
    "filled",
    "samebarsltpcollision",
    "realizedr",
    "commission",
    "spreadcost",
    "slippagecost",
}
ALLOWED_MANIFEST_KEYS = {
    "strategy", "instrument", "timeframe", "parameters", "data_version",
    "optimizer_version", "claimed_config_hash", "change_scope", "dataset_sha256", "dataset_path",
    "report_path", "candidate_csv", "run_id", "signal_id_epoch_basis",
    "server_utc_offset_minutes", "provenance", "folds", "excluded_windows",
    "parameter_neighbors", "feature_importance", "clustered_mda", "counterfactual",
    "paired_test_p_value", "scale_out",
}


class BuildEvidenceError(ValueError):
    """Manifest/Tester export cannot be normalized safely."""


def _canonical_column(value: str) -> str:
    return "".join(char.lower() for char in value.strip() if char.isalnum())


def _parse_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise BuildEvidenceError(f"{name} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise BuildEvidenceError(f"{name} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BuildEvidenceError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise BuildEvidenceError(f"cannot read file for SHA-256 digest: {path}") from exc
    return digest.hexdigest()


def _resolve_path(manifest_path: Path, value: object, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise BuildEvidenceError(f"{name} must be a file path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = manifest_path.parent / path
    path = path.resolve()
    if not path.is_file():
        raise BuildEvidenceError(f"{name} does not exist or is not a file: {path}")
    return path


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildEvidenceError(f"cannot read valid UTF-8 JSON manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise BuildEvidenceError("manifest root must be a JSON object")
    unknown = sorted(set(payload) - ALLOWED_MANIFEST_KEYS)
    if unknown:
        raise BuildEvidenceError(f"manifest contains unsupported keys: {', '.join(unknown)}")
    required = {
        "strategy", "instrument", "timeframe", "parameters", "data_version",
        "optimizer_version", "dataset_sha256", "report_path", "candidate_csv",
        "run_id", "signal_id_epoch_basis", "provenance", "folds",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise BuildEvidenceError(f"manifest is missing required fields: {', '.join(missing)}")
    for key in ("strategy", "instrument", "timeframe", "data_version", "optimizer_version", "run_id"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise BuildEvidenceError(f"{key} must be a non-empty string")
    if not isinstance(payload["parameters"], dict) or not payload["parameters"]:
        raise BuildEvidenceError("parameters must be a non-empty JSON object")
    if not SHA256_RE.fullmatch(str(payload["dataset_sha256"])):
        raise BuildEvidenceError("dataset_sha256 must be a 64-character SHA-256 hex digest")
    if payload["signal_id_epoch_basis"] not in {"unix_utc", "broker_wall_clock"}:
        raise BuildEvidenceError("signal_id_epoch_basis must be unix_utc or broker_wall_clock")
    offset = payload.get("server_utc_offset_minutes")
    if payload["signal_id_epoch_basis"] == "broker_wall_clock":
        if not isinstance(offset, int) or isinstance(offset, bool) or not -840 <= offset <= 840:
            raise BuildEvidenceError(
                "broker_wall_clock timestamps require server_utc_offset_minutes in [-840, 840]"
            )
    elif offset is not None and (
        not isinstance(offset, int) or isinstance(offset, bool) or not -840 <= offset <= 840
    ):
        raise BuildEvidenceError("server_utc_offset_minutes must be within [-840, 840]")
    if not isinstance(payload["provenance"], dict):
        raise BuildEvidenceError("provenance must be a JSON object")
    if not isinstance(payload["folds"], list) or len(payload["folds"]) < 3:
        raise BuildEvidenceError("at least three explicit walk-forward folds are required")
    return payload


def _load_csv(path: Path, manifest: dict[str, Any]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise BuildEvidenceError(f"Tester CSV has no header: {path}")
            normalized_headers = {_canonical_column(value): value for value in reader.fieldnames if value}
            missing = sorted(REQUIRED_CSV_COLUMNS - set(normalized_headers))
            if missing:
                raise BuildEvidenceError(
                    f"{path.name} is missing required OutcomeTracker columns: {', '.join(missing)}"
                )
            rows = []
            seen_ids: set[str] = set()
            for line_number, raw in enumerate(reader, start=2):
                row = {
                    canonical: (raw.get(original) or "").strip()
                    for canonical, original in normalized_headers.items()
                }
                signal_id = row["signalid"]
                if not signal_id:
                    raise BuildEvidenceError(f"{path.name}:{line_number}: SignalID is empty")
                if signal_id in seen_ids:
                    raise BuildEvidenceError(f"{path.name}:{line_number}: duplicate SignalID {signal_id!r}")
                seen_ids.add(signal_id)
                symbol = row["symbol"]
                if symbol.casefold() != manifest["instrument"].casefold():
                    raise BuildEvidenceError(
                        f"{path.name}:{line_number}: Symbol {symbol!r} does not match manifest instrument "
                        f"{manifest['instrument']!r}"
                    )
                timeframe = _normalize_timeframe(row["entrytf"])
                if timeframe and timeframe.casefold() != manifest["timeframe"].casefold():
                    raise BuildEvidenceError(
                        f"{path.name}:{line_number}: EntryTF {row['entrytf']!r} does not match manifest "
                        f"timeframe {manifest['timeframe']!r}"
                    )
                if row["direction"].upper() not in {"BUY", "SELL"}:
                    raise BuildEvidenceError(f"{path.name}:{line_number}: invalid Direction")
                timestamp = _timestamp_from_signal_id(signal_id, manifest, path.name, line_number)
                is_filled = _parse_bool(row["filled"], path.name, line_number, "Filled")
                ambiguous = _parse_bool(
                    row["samebarsltpcollision"], path.name, line_number, "SameBarSLTPCollision"
                ) or row.get("outcome", "").strip().casefold() == "ambiguous"
                if not is_filled:
                    outcome = "no_fill"
                    realized_r = None
                elif ambiguous:
                    outcome = "ambiguous"
                    realized_r = None
                else:
                    realized_r_value = _parse_finite_float(row["realizedr"], path.name, line_number, "RealizedR")
                    if realized_r_value > 1e-6:
                        outcome = "win"
                    elif realized_r_value < -1e-6:
                        outcome = "loss"
                    else:
                        outcome = "scratch"
                        realized_r_value = 0.0
                    realized_r = realized_r_value

                costs = {}
                for label, key in (
                    ("Commission", "commission"),
                    ("SpreadCost", "spreadcost"),
                    ("SlippageCost", "slippagecost"),
                ):
                    if is_filled:
                        value = _parse_finite_float(row[key], path.name, line_number, label)
                        if value < 0:
                            raise BuildEvidenceError(f"{path.name}:{line_number}: {label} cannot be negative")
                        costs[{"Commission": "commission_cost", "SpreadCost": "spread_cost",
                               "SlippageCost": "slippage_cost"}[label]] = value
                    else:
                        costs[{"Commission": "commission_cost", "SpreadCost": "spread_cost",
                               "SlippageCost": "slippage_cost"}[label]] = None
                rows.append({
                    "trade_id": signal_id,
                    "timestamp": timestamp,
                    "outcome": outcome,
                    "realized_r": realized_r,
                    "filled": is_filled,
                    **costs,
                })
            return rows
    except OSError as exc:
        raise BuildEvidenceError(f"cannot read Tester CSV: {path}") from exc


def _normalize_timeframe(value: str) -> str:
    upper = value.strip().upper()
    if upper.startswith("PERIOD_"):
        upper = upper[len("PERIOD_"):]
    return upper


def _parse_bool(value: str, filename: str, line: int, field: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"yes", "true", "1", "y"}:
        return True
    if normalized in {"no", "false", "0", "n"}:
        return False
    raise BuildEvidenceError(f"{filename}:{line}: {field} must be Yes/No, true/false, or 1/0")


def _parse_finite_float(value: str, filename: str, line: int, field: str) -> float:
    try:
        result = float(value.strip())
    except (ValueError, AttributeError) as exc:
        raise BuildEvidenceError(f"{filename}:{line}: {field} must be numeric") from exc
    if not math.isfinite(result):
        raise BuildEvidenceError(f"{filename}:{line}: {field} must be finite")
    return result


def _timestamp_from_signal_id(
    signal_id: str, manifest: dict[str, Any], filename: str, line: int
) -> datetime:
    suffix = signal_id.rpartition("_")[2]
    try:
        epoch = int(suffix)
    except ValueError as exc:
        raise BuildEvidenceError(
            f"{filename}:{line}: SignalID must end in the numeric epoch suffix written by SignalLogger"
        ) from exc
    try:
        timestamp = datetime.fromtimestamp(epoch, timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise BuildEvidenceError(f"{filename}:{line}: SignalID epoch suffix is out of range") from exc
    if manifest["signal_id_epoch_basis"] == "broker_wall_clock":
        timestamp -= timedelta(minutes=manifest["server_utc_offset_minutes"])
    return timestamp


def _validate_folds(manifest: dict[str, Any], period_start: datetime, oos_start: datetime) -> list[dict[str, Any]]:
    normalized = []
    seen_ids = set()
    for item in manifest["folds"]:
        if not isinstance(item, dict):
            raise BuildEvidenceError("each folds item must be an object")
        fold_id = item.get("fold_id")
        if not isinstance(fold_id, int) or isinstance(fold_id, bool) or not 1 <= fold_id <= 1000:
            raise BuildEvidenceError("fold_id must be an integer between 1 and 1000")
        if fold_id in seen_ids:
            raise BuildEvidenceError(f"duplicate fold_id {fold_id}")
        seen_ids.add(fold_id)
        train_start = _parse_datetime(item.get("train_start"), f"fold {fold_id} train_start")
        train_end = _parse_datetime(item.get("train_end"), f"fold {fold_id} train_end")
        validation_start = _parse_datetime(item.get("validation_start"), f"fold {fold_id} validation_start")
        validation_end = _parse_datetime(item.get("validation_end"), f"fold {fold_id} validation_end")
        if not (period_start <= train_start < train_end <= validation_start < validation_end <= oos_start):
            raise BuildEvidenceError(
                f"fold {fold_id} must use ordered, non-overlapping train then validation windows before locked OOS"
            )
        normalized.append({
            "fold_id": fold_id,
            "train_start": train_start,
            "train_end": train_end,
            "validation_start": validation_start,
            "validation_end": validation_end,
        })
    return sorted(normalized, key=lambda item: item["fold_id"])


def _contains(timestamp: datetime, start: datetime, end: datetime) -> bool:
    return start <= timestamp < end


def _normalize_candidate_trades(
    rows: list[dict[str, Any]],
    folds: list[dict[str, Any]],
    *,
    period_start: datetime,
    period_end: datetime,
    oos_start: datetime,
    oos_end: datetime,
    excluded_windows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    output = []
    excluded_count = 0
    for row in rows:
        timestamp = row["timestamp"]
        if not period_start <= timestamp <= period_end:
            raise BuildEvidenceError(f"trade {row['trade_id']} lies outside the declared backtest period")
        matched = False
        if _contains(timestamp, oos_start, oos_end):
            output.append({**row, "timestamp": _iso(timestamp), "partition": "locked_oos", "fold_id": None})
            matched = True
        else:
            for fold in folds:
                if _contains(timestamp, fold["train_start"], fold["train_end"]):
                    output.append({
                        **row, "timestamp": _iso(timestamp),
                        "partition": "train", "fold_id": fold["fold_id"],
                    })
                    matched = True
                if _contains(timestamp, fold["validation_start"], fold["validation_end"]):
                    output.append({
                        **row, "timestamp": _iso(timestamp),
                        "partition": "validation", "fold_id": fold["fold_id"],
                    })
                    matched = True
        if not matched:
            if not any(
                _contains(
                    timestamp,
                    _parse_datetime(window.get("start"), "excluded window start"),
                    _parse_datetime(window.get("end"), "excluded window end"),
                )
                for window in excluded_windows
            ):
                raise BuildEvidenceError(
                    f"trade {row['trade_id']} is not assigned to a declared fold/OOS window; "
                    "add an explicit excluded warm-up/embargo window if intentional"
                )
            excluded_count += 1
    return output, excluded_count


def _normalize_neighbors(
    manifest_path: Path,
    neighbors: object,
    manifest: dict[str, Any],
    provenance: dict[str, Any],
    oos_start: datetime,
    oos_end: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(neighbors, list):
        raise BuildEvidenceError("parameter_neighbors must be a JSON array")
    normalized = []
    summaries = []
    for index, item in enumerate(neighbors, start=1):
        if not isinstance(item, dict):
            raise BuildEvidenceError("each parameter_neighbors item must be an object")
        parameters = item.get("parameters")
        if not isinstance(parameters, dict) or not parameters:
            raise BuildEvidenceError(f"parameter neighbor {index} requires non-empty parameters")
        report_path = _resolve_path(manifest_path, item.get("report_path"), f"neighbor {index} report_path")
        csv_path = _resolve_path(manifest_path, item.get("csv_path"), f"neighbor {index} csv_path")
        report_hash = _digest_file(report_path)
        claimed_hash = item.get("report_sha256")
        if claimed_hash is not None and str(claimed_hash).lower() != report_hash:
            raise BuildEvidenceError(f"parameter neighbor {index} report_sha256 does not match its report file")
        rows = _load_csv(csv_path, manifest)
        neighbor_trades = []
        for row in rows:
            timestamp = row["timestamp"]
            if not _contains(timestamp, oos_start, oos_end):
                continue
            if row["outcome"] not in {"win", "loss", "scratch"}:
                continue
            neighbor_trades.append({
                "trade_id": row["trade_id"],
                "timestamp": _iso(timestamp),
                "outcome": row["outcome"],
                "realized_r": row["realized_r"],
            })
        normalized.append({
            "parameters": parameters,
            "report_sha256": report_hash,
            "outcome_csv_sha256": _digest_file(csv_path),
            "dataset_sha256": declared_dataset_sha,
            "ea_source_commit": provenance["ea_source_commit"],
            "ea_build": provenance["ea_build"],
            "terminal_build": provenance["terminal_build"],
            "period_start": provenance["period_start"],
            "period_end": provenance["period_end"],
            "trades": neighbor_trades,
        })
        summaries.append({
            "index": index,
            "csv_rows": len(rows),
            "locked_oos_resolved_rows": len(neighbor_trades),
            "report_sha256": report_hash,
            "outcome_csv_sha256": _digest_file(csv_path),
        })
    return normalized, summaries


def build_evidence(manifest_path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(manifest_path).expanduser().resolve()
    manifest = _read_manifest(path)
    report_path = _resolve_path(path, manifest["report_path"], "report_path")
    candidate_csv = _resolve_path(path, manifest["candidate_csv"], "candidate_csv")
    declared_dataset_sha = str(manifest["dataset_sha256"]).lower()
    dataset_digest_status = "declared_manifest_only"
    if manifest.get("dataset_path") is not None:
        dataset_path = _resolve_path(path, manifest["dataset_path"], "dataset_path")
        actual_dataset_sha = _digest_file(dataset_path)
        if actual_dataset_sha != declared_dataset_sha:
            raise BuildEvidenceError(
                "dataset_sha256 does not match the supplied dataset_path file digest"
            )
        dataset_digest_status = "verified_from_dataset_file"
    provenance_raw = dict(manifest["provenance"])
    allowed_provenance = {
        "ea_source_commit", "ea_build", "terminal_build", "data_vendor",
        "period_start", "period_end", "locked_oos_start", "locked_oos_end",
        "generated_at", "spread_model", "spread_points", "commission_per_lot",
        "slippage_points", "fill_policy",
    }
    unknown_provenance = sorted(set(provenance_raw) - allowed_provenance)
    if unknown_provenance:
        raise BuildEvidenceError(f"unsupported provenance fields: {', '.join(unknown_provenance)}")
    missing_provenance = sorted(allowed_provenance - set(provenance_raw))
    if missing_provenance:
        raise BuildEvidenceError(f"provenance is missing fields: {', '.join(missing_provenance)}")
    provenance = {key: provenance_raw[key] for key in allowed_provenance}
    period_start = _parse_datetime(provenance["period_start"], "provenance.period_start")
    period_end = _parse_datetime(provenance["period_end"], "provenance.period_end")
    oos_start = _parse_datetime(provenance["locked_oos_start"], "provenance.locked_oos_start")
    oos_end = _parse_datetime(provenance["locked_oos_end"], "provenance.locked_oos_end")
    if not period_start <= oos_start < oos_end <= period_end:
        raise BuildEvidenceError("locked OOS window must be inside the declared backtest period")
    folds = _validate_folds(manifest, period_start, oos_start)
    excluded_windows = manifest.get("excluded_windows", [])
    if not isinstance(excluded_windows, list):
        raise BuildEvidenceError("excluded_windows must be a JSON array")
    raw_rows = _load_csv(candidate_csv, manifest)
    trades, excluded_count = _normalize_candidate_trades(
        raw_rows, folds, period_start=period_start, period_end=period_end,
        oos_start=oos_start, oos_end=oos_end, excluded_windows=excluded_windows,
    )
    generated_at = _parse_datetime(provenance["generated_at"], "provenance.generated_at")
    api_provenance = {
        "source": "MT5_STRATEGY_TESTER",
        "run_id": manifest["run_id"],
        "report_sha256": _digest_file(report_path),
        "outcome_csv_sha256": _digest_file(candidate_csv),
        "dataset_sha256": declared_dataset_sha,
        **{key: value for key, value in provenance.items()},
    }
    for key in ("period_start", "period_end", "locked_oos_start", "locked_oos_end", "generated_at"):
        api_provenance[key] = _iso(_parse_datetime(api_provenance[key], f"provenance.{key}"))
    neighbor_payload, neighbor_summary = _normalize_neighbors(
        path, manifest.get("parameter_neighbors", []), manifest, api_provenance, oos_start, oos_end,
    )
    payload = {
        "strategy": manifest["strategy"],
        "instrument": manifest["instrument"],
        "timeframe": _normalize_timeframe(manifest["timeframe"]),
        "parameters": manifest["parameters"],
        "data_version": manifest["data_version"],
        "optimizer_version": manifest["optimizer_version"],
        "change_scope": manifest.get("change_scope", "ENTRY"),
        "provenance": api_provenance,
        "trades": trades,
        "parameter_neighbors": neighbor_payload,
        "feature_importance": manifest.get("feature_importance", []),
        "clustered_mda": manifest.get("clustered_mda", []),
        "counterfactual": manifest.get("counterfactual", []),
        "scale_out": manifest.get("scale_out", []),
    }
    for key in ("claimed_config_hash", "paired_test_p_value"):
        if key in manifest:
            payload[key] = manifest[key]
    summary = {
        "status": "built",
        "run_id": manifest["run_id"],
        "candidate_csv_sha256": api_provenance["outcome_csv_sha256"],
        "dataset_digest_status": dataset_digest_status,
        "report_sha256": api_provenance["report_sha256"],
        "csv_source_rows": len(raw_rows),
        "normalized_partition_rows": len(trades),
        "excluded_warmup_or_embargo_rows": excluded_count,
        "fold_count": len(folds),
        "locked_oos_start": _iso(oos_start),
        "locked_oos_end": _iso(oos_end),
        "parameter_neighbors": neighbor_summary,
        "destination_file_not_sent": True,
        "evidence_gaps_to_check": [
            key for key in ("feature_importance", "clustered_mda", "counterfactual")
            if not payload[key]
        ],
        "scale_out_rows": len(payload["scale_out"]),
    }
    return payload, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Manifest with report, CSV, windows, and research artifacts")
    parser.add_argument("--output", required=True, help="Output normalized evidence JSON path")
    args = parser.parse_args()
    try:
        payload, summary = build_evidence(args.manifest)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    except (BuildEvidenceError, OSError, TypeError, ValueError) as exc:
        print(f"build_tester_evidence: {exc}", file=sys.stderr)
        return 1
    summary["output_file"] = str(output)
    summary["normalized_payload_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
