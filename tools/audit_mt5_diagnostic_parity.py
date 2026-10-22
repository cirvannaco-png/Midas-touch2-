#!/usr/bin/env python3
"""Audit paired MT5 diagnostic OFF/ON exports without fabricating evidence.

The tool verifies matched run context, proves the presets differ only in the
declared diagnostic input, rejects synthetic/no-history tester logs, requires
complete cost fields, and measures signal-to-decision/outcome attribution. It
does not run MT5, calculate strategy profitability, or authorize promotion.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DIAGNOSTIC_FIELDS = {
    "contradictionpenalty", "envscore", "execscore", "envexecconfidence",
    "confidencedecayed", "decaybars",
}
VOLATILE_DECISION_FIELDS = {
    "decisionid", "executionid", "correlationid", "runid", "traceid",
    "createdat", "updatedat", "loggedat", "generatedat", "decisionfingerprint",
}
CONTEXT_KEYS = {
    "symbol", "timeframe", "period_start", "period_end",
    "locked_oos_start", "locked_oos_end", "dataset_sha256", "ea_source_sha",
    "ea_build", "terminal_build", "data_vendor", "tester_model", "spread_model",
    "spread_widening_multiplier", "spread_points", "baseline_spread_points",
    "cash_per_point_per_lot", "commission_per_lot", "slippage_points",
    "swap_included", "base_costs_applied_in_tester",
    "stress_costs_applied_in_analysis", "fill_policy", "initial_balance",
    "account_currency", "leverage", "diagnostic_inputs",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
BAD_LOG_PATTERNS = (
    re.compile(r"mathematical\s+test\s+mode", re.I),
    re.compile(r"no\s+(?:market\s+)?history(?:\s+data)?", re.I),
    re.compile(r"no\s+symbol\s+information", re.I),
    re.compile(r"symbol\s+information\s+(?:is\s+)?not\s+available", re.I),
    re.compile(r"history\s+data\s+is\s+not\s+found", re.I),
    re.compile(r"failed\s+to\s+(?:load|download)\s+(?:market\s+)?history", re.I),
    re.compile(r"cannot\s+(?:load|get)\s+(?:market\s+)?history", re.I),
    re.compile(r"no\s+ticks?\s+(?:available|found)", re.I),
)
ALIASES = {
    "signalid": ("signalid", "signal_id"),
    "decisionid": ("decisionid", "decision_id"),
    "positionid": ("positionid", "position_id", "positionidentifier", "position_identifier"),
    "dealid": ("dealid", "deal_id", "dealticket", "deal_ticket", "ticket", "deal"),
    "entry": ("entry", "dealentry", "deal_entry", "entrytype", "entry_type"),
    "time": ("time", "dealtime", "deal_time", "timestamp"),
}


class AuditError(ValueError):
    """Evidence is missing, malformed, or cannot support this audit."""


def _canon(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def _parse_time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise AuditError(f"{name} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditError(f"{name} is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AuditError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise AuditError(f"cannot read artifact: {path}") from exc
    return digest.hexdigest()


def _resolve(base: Path, value: object, name: str, *, allow_empty: bool = False) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise AuditError(f"{name} must be a file path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base.parent / path
    path = path.resolve()
    if not path.is_file():
        raise AuditError(f"{name} is missing or is not a file: {path}")
    if not allow_empty and path.stat().st_size == 0:
        raise AuditError(f"{name} is empty: {path}")
    return path


def _number(value: object, name: str, *, positive: bool = False, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise AuditError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise AuditError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise AuditError(f"{name} must be a finite number")
    if positive and result <= 0:
        raise AuditError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise AuditError(f"{name} must be at least {minimum}")
    return result


def _context(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise AuditError("test_context must be an object")
    missing = sorted(CONTEXT_KEYS - set(raw))
    extra = sorted(set(raw) - CONTEXT_KEYS)
    if missing or extra:
        raise AuditError(f"test_context keys invalid: missing={missing}, extra={extra}")
    result = dict(raw)
    for key in (
        "symbol", "timeframe", "ea_build", "terminal_build", "data_vendor",
        "tester_model", "spread_model", "fill_policy", "account_currency", "leverage",
    ):
        if not isinstance(result[key], str) or not result[key].strip():
            raise AuditError(f"test_context.{key} must be a non-empty string")
        result[key] = result[key].strip()
    result["dataset_sha256"] = str(result["dataset_sha256"]).lower()
    result["ea_source_sha"] = str(result["ea_source_sha"]).lower()
    if not SHA256_RE.fullmatch(result["dataset_sha256"]):
        raise AuditError("test_context.dataset_sha256 must be SHA-256")
    if not SOURCE_SHA_RE.fullmatch(result["ea_source_sha"]):
        raise AuditError("test_context.ea_source_sha must be a commit SHA")
    for key in ("period_start", "period_end", "locked_oos_start", "locked_oos_end"):
        result[key] = _parse_time(result[key], f"test_context.{key}")
    if not (
        result["period_start"] < result["locked_oos_start"]
        < result["locked_oos_end"] <= result["period_end"]
    ):
        raise AuditError(
            "require period_start < locked_oos_start < locked_oos_end <= period_end"
        )
    for key in ("baseline_spread_points", "cash_per_point_per_lot", "commission_per_lot",
                "slippage_points", "initial_balance", "spread_widening_multiplier"):
        result[key] = _number(result[key], f"test_context.{key}", positive=True)
    if result["spread_widening_multiplier"] <= 1.01:
        raise AuditError("spread_widening_multiplier must be greater than 1.01")
    if result["spread_points"] is None:
        if result["spread_model"] not in {"real_ticks_plus_stress", "real_ticks"}:
            raise AuditError("spread_points may be null only for a real-tick spread model")
    else:
        result["spread_points"] = _number(result["spread_points"], "test_context.spread_points", minimum=0)
    diagnostic_inputs = result["diagnostic_inputs"]
    if not isinstance(diagnostic_inputs, dict) or not diagnostic_inputs:
        raise AuditError("test_context.diagnostic_inputs must map one or more real MT5 input names to OFF/ON values")
    normalized_inputs = {}
    for input_name, pair in diagnostic_inputs.items():
        if not isinstance(input_name, str) or not input_name.strip() or not isinstance(pair, dict) or set(pair) != {"off", "on"}:
            raise AuditError("each diagnostic_inputs entry must contain exactly off and on values")
        values = {}
        for mode in ("off", "on"):
            raw_value = pair[mode]
            if isinstance(raw_value, (dict, list)) or raw_value is None:
                raise AuditError(f"diagnostic_inputs.{input_name}.{mode} must be a scalar .set value")
            values[mode] = str(raw_value).strip()
        if not values["off"] or not values["on"] or values["off"].casefold() == values["on"].casefold():
            raise AuditError(f"diagnostic input {input_name} must differ between OFF and ON")
        normalized_inputs[input_name.strip()] = values
    result["diagnostic_inputs"] = normalized_inputs
    for key in ("swap_included", "base_costs_applied_in_tester", "stress_costs_applied_in_analysis"):
        if result[key] is not True:
            raise AuditError(f"test_context.{key} must be true; missing costs cannot be assumed away")
    if result["spread_model"] not in {"real_ticks_plus_stress", "variable_spread_stress", "real_ticks"}:
        raise AuditError("test_context.spread_model must identify the actual spread model")
    return result


def _read_csv(path: Path, name: str) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise AuditError(f"{name} has no CSV header")
            header = [_canon(field) for field in reader.fieldnames if field is not None]
            if len(header) != len(set(header)):
                raise AuditError(f"{name} has duplicate/ambiguous normalized CSV headers")
            rows: list[dict[str, str]] = []
            for line_no, raw in enumerate(reader, start=2):
                if None in raw:
                    raise AuditError(f"{name}:{line_no} has extra fields beyond its header")
                rows.append({
                    _canon(key): (value or "").strip()
                    for key, value in raw.items() if key is not None
                })
            return header, rows
    except OSError as exc:
        raise AuditError(f"cannot read {name}: {path}") from exc
    except UnicodeDecodeError as exc:
        raise AuditError(f"{name} must be UTF-8 CSV: {path}") from exc


def _field(header: list[str], name: str) -> str:
    aliases = {_canon(item) for item in ALIASES.get(name, (name,))}
    for item in header:
        if item in aliases:
            return item
    raise AuditError(f"CSV is missing required {name} column (accepted aliases: {sorted(aliases)})")


def _preset(path: Path) -> dict[str, tuple[str, tuple[str, ...]]]:
    values: dict[str, tuple[str, tuple[str, ...]]] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise AuditError(f"cannot read UTF-8 MT5 .set preset: {path}") from exc
    for line_no, line in enumerate(lines, 1):
        row = line.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, raw_value = row.split("=", 1)
        key = key.strip()
        if not key or key in values:
            raise AuditError(f"empty or duplicate preset key at {path}:{line_no}")
        parts = tuple(part.strip() for part in raw_value.split("||"))
        value = parts[0].lower() if parts[0].lower() in {"true", "false"} else parts[0]
        values[key] = (value, parts[1:])
    if not values:
        raise AuditError(f"preset has no key=value inputs: {path}")
    return values


def _same_setting(left: tuple[str, tuple[str, ...]], right: tuple[str, tuple[str, ...]]) -> bool:
    def normalize(value: str) -> str:
        if value.lower() in {"true", "false"}:
            return value.lower()
        try:
            number = float(value)
        except ValueError:
            return value.strip()
        return format(number, ".12g") if math.isfinite(number) else value.strip()
    return normalize(left[0]) == normalize(right[0]) and left[1] == right[1]


def _check_preset_pair(off_path: Path, on_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    off, on = _preset(off_path), _preset(on_path)
    expected = context["diagnostic_inputs"]
    if set(off) != set(on):
        raise AuditError("diagnostic OFF/ON preset key sets differ")
    missing = sorted(set(expected) - set(off))
    if missing:
        raise AuditError("diagnostic input(s) absent from exported .set presets: " + ", ".join(missing))
    changed = []
    report_inputs = {}
    for name, modes in expected.items():
        expected_off, expected_on = modes["off"], modes["on"]
        if _same_setting(off[name], on[name]):
            raise AuditError(f"declared diagnostic input {name} does not differ between presets")
        if off[name][1] != on[name][1]:
            raise AuditError(f"diagnostic input {name} differs in optimizer metadata, not only its active value")
        if not _same_setting((off[name][0], ()), (expected_off, ())) or not _same_setting((on[name][0], ()), (expected_on, ())):
            raise AuditError(f"{name} preset values do not match test_context diagnostic_inputs")
        report_inputs[name] = {"off_value": off[name][0], "on_value": on[name][0]}
    for name in sorted(off):
        if not _same_setting(off[name], on[name]):
            changed.append(name)
    if set(changed) != set(expected):
        extra = sorted(set(changed) - set(expected))
        unchanged = sorted(set(expected) - set(changed))
        details = []
        if extra:
            details.append("additional inputs changed: " + ", ".join(extra))
        if unchanged:
            details.append("declared diagnostic inputs unchanged: " + ", ".join(unchanged))
        raise AuditError("diagnostic OFF/ON presets are not an isolated ablation (" + "; ".join(details) + ")")
    return {
        "diagnostic_inputs": report_inputs,
        "only_declared_diagnostic_inputs_changed": True,
        "off_preset_sha256": _hash(off_path),
        "on_preset_sha256": _hash(on_path),
    }


def _row_index(rows: list[dict[str, str]], key: str, name: str, *, allow_empty: bool = True) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for i, row in enumerate(rows, start=2):
        value = (row.get(key) or "").strip()
        if not value:
            raise AuditError(f"{name} row {i} has an empty {key}")
        if value in indexed:
            raise AuditError(f"{name} contains duplicate {key}: {value}")
        indexed[value] = row
    if not allow_empty and not indexed:
        raise AuditError(f"{name} contains no data rows")
    return indexed


def _bool(value: str, name: str) -> bool:
    norm = value.strip().lower()
    if norm in {"true", "yes", "1"}:
        return True
    if norm in {"false", "no", "0"}:
        return False
    raise AuditError(f"{name} must be Yes/No, True/False, or 1/0")


def _validate_signals(header: list[str], rows: list[dict[str, str]], role: str) -> dict[str, dict[str, str]]:
    required = {"symbol", "entrytf", "datetime", "direction"}
    missing = sorted(required - set(header))
    if missing:
        raise AuditError(f"{role} signal CSV missing required columns: {', '.join(missing)}")
    key = _field(header, "signalid")
    return _row_index(rows, key, f"{role} signals")


def _validate_outcomes(header: list[str], rows: list[dict[str, str]], role: str) -> dict[str, dict[str, str]]:
    required = {"outcome", "outcomeepoch", "filled", "realizednetpnl", "realizedr",
                "commission", "spreadcost", "slippagecost"}
    missing = sorted(required - set(header))
    if missing:
        raise AuditError(f"{role} outcome CSV missing required columns: {', '.join(missing)}")
    signal_key = _field(header, "signalid")
    indexed = _row_index(rows, signal_key, f"{role} outcomes")
    for signal_id, row in indexed.items():
        filled = _bool(row["filled"], f"{role} outcome {signal_id}.Filled")
        epoch = _number(row["outcomeepoch"], f"{role} outcome {signal_id}.OutcomeEpoch")
        if epoch <= 0:
            raise AuditError(f"{role} outcome {signal_id} has no valid resolution epoch")
        for key in ("realizednetpnl", "realizedr"):
            _number(row[key], f"{role} outcome {signal_id}.{key}")
        if filled:
            for key in ("commission", "spreadcost", "slippagecost"):
                _number(row[key], f"{role} filled outcome {signal_id}.{key}")
    return indexed


def _validate_decisions(header: list[str], rows: list[dict[str, str]], role: str) -> dict[str, dict[str, str]]:
    required = {"decision"}
    missing = sorted(required - set(header))
    if missing:
        raise AuditError(f"{role} decision CSV missing required columns: {', '.join(missing)}")
    signal_key, decision_key = _field(header, "signalid"), _field(header, "decisionid")
    by_signal = _row_index(rows, signal_key, f"{role} decisions")
    # The EA uses DecisionID=0 for ignored/rejected decisions before the router
    # allocates a durable decision identifier. Zero is intentionally repeatable;
    # positive IDs must remain unique within a run.
    seen: set[str] = set()
    for line_no, row in enumerate(rows, start=2):
        value = (row.get(decision_key) or "").strip()
        if not value:
            raise AuditError(f"{role} decision row {line_no} has an empty DecisionID")
        if value in {"0", "-1"}:
            continue
        if value in seen:
            raise AuditError(f"{role} decisions contain duplicate non-zero DecisionID: {value}")
        seen.add(value)
    return by_signal


def _validate_deals(header: list[str], rows: list[dict[str, str]], role: str) -> dict[str, Any]:
    required = {"positionid", "time", "entry", "volume", "profit", "commission", "swap", "fee"}
    resolved = {key: _field(header, key) for key in required}
    deal_key = _field(header, "dealid")
    position_key = resolved["positionid"]
    net = gross = commission = swap = fee = turnover = 0.0
    deal_ids: set[str] = set()
    position_ids: set[str] = set()
    for line_no, row in enumerate(rows, start=2):
        deal_id = (row.get(deal_key) or "").strip()
        if not deal_id:
            raise AuditError(f"{role} deals row {line_no} has no deal ticket/id")
        if deal_id in deal_ids:
            raise AuditError(f"{role} deals has duplicate deal ticket/id {deal_id}")
        deal_ids.add(deal_id)
        pos = (row.get(position_key) or "").strip()
        if not pos:
            raise AuditError(f"{role} deals row {line_no} has no position_id")
        position_ids.add(pos)
        _parse_time(row.get(resolved["time"]), f"{role} deals row {line_no}.time")
        entry = _canon(row.get(resolved["entry"], ""))
        if entry not in {"in", "out", "outby", "dealentryin", "dealentryout", "dealentryoutby", "0", "1", "3"}:
            raise AuditError(f"{role} deals row {line_no} has unsupported entry type")
        volume = _number(row.get(resolved["volume"]), f"{role} deals row {line_no}.volume", positive=True)
        values = {
            key: _number(row.get(resolved[key]), f"{role} deals row {line_no}.{key}")
            for key in ("profit", "commission", "swap", "fee")
        }
        gross += values["profit"]
        commission += values["commission"]
        swap += values["swap"]
        fee += values["fee"]
        turnover += volume
        net += sum(values.values())
    return {
        "deal_rows": len(rows),
        "unique_deal_ids": len(deal_ids),
        "position_id_groups": len(position_ids),
        "cost_fields_explicit_and_finite": True,
        "gross_price_pnl_cash": round(gross, 8),
        "commission_cashflow": round(commission, 8),
        "swap_cashflow": round(swap, 8),
        "broker_fee_cashflow": round(fee, 8),
        "deal_turnover_volume_sum": round(turnover, 8),
        "net_deal_cashflow_before_incremental_stress": round(net, 8),
        "spread_and_slippage_stress_note": (
            "This audit validates actual exported cashflows but does not apply stress twice. "
            "Run the matched risk/trailing experiment for predeclared incremental stress."
        ),
    }


def _deal_group_signatures(header: list[str], rows: list[dict[str, str]]) -> list[str]:
    """Build position-level execution signatures while ignoring run-local ticket IDs."""
    position_key = _field(header, "positionid")
    time_key = _field(header, "time")
    entry_key = _field(header, "entry")
    fields = {key: _field(header, key) for key in ("volume", "profit", "commission", "swap", "fee")}
    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for line_no, row in enumerate(rows, start=2):
        position_id = (row.get(position_key) or "").strip()
        entry = _canon(row.get(entry_key, ""))
        if entry in {"0", "dealentryin", "entryin"}:
            entry = "in"
        elif entry in {"1", "dealentryout", "entryout"}:
            entry = "out"
        elif entry in {"3", "dealentryoutby", "entryoutby"}:
            entry = "outby"
        stamp = _iso(_parse_time(row.get(time_key), f"deal row {line_no}.time"))
        numbers = tuple(
            round(_number(row.get(fields[key]), f"deal row {line_no}.{key}"), 10)
            for key in ("volume", "profit", "commission", "swap", "fee")
        )
        grouped.setdefault(position_id, []).append((stamp, entry, *numbers))
    signatures = [
        json.dumps(sorted(group), separators=(",", ":"), allow_nan=False)
        for group in grouped.values()
    ]
    return sorted(signatures)


def _compare_deal_groups(off_header: list[str], off_rows: list[dict[str, str]],
                         on_header: list[str], on_rows: list[dict[str, str]]) -> dict[str, Any]:
    """Compare position economics without requiring ticket numbers to match between runs."""
    off_groups = _deal_group_signatures(off_header, off_rows)
    on_groups = _deal_group_signatures(on_header, on_rows)
    off_count, on_count = Counter(off_groups), Counter(on_groups)
    removed = list((off_count - on_count).elements())
    added = list((on_count - off_count).elements())
    return {
        "off_position_groups": len(off_groups),
        "on_position_groups": len(on_groups),
        "groups_added_when_diagnostic_on": len(added),
        "groups_missing_when_diagnostic_on": len(removed),
        "economic_signatures_identical": not added and not removed,
        "note": "Deal tickets and position identifiers are run-local; comparison uses timestamp, entry/exit type, volume, profit, commission, swap, and fee per position.",
    }


def _validate_log(path: Path, context: dict[str, Any], role: str) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    findings = []
    for pattern in BAD_LOG_PATTERNS:
        match = pattern.search(raw)
        if match:
            findings.append(f"{role} tester log indicates unavailable/synthetic market data: {match.group(0)}")
    if context["symbol"].casefold() not in raw.casefold():
        findings.append(f"{role} tester log does not mention test symbol {context['symbol']}")
    return findings


def _compare(
    off: dict[str, dict[str, str]],
    on: dict[str, dict[str, str]],
    *,
    ignore_fields: set[str],
) -> dict[str, Any]:
    off_ids, on_ids = set(off), set(on)
    common = off_ids & on_ids
    changes = []
    for row_id in sorted(common):
        a, b = off[row_id], on[row_id]
        fields = sorted((set(a) | set(b)) - ignore_fields)
        changed = [field for field in fields if a.get(field, "") != b.get(field, "")]
        if changed:
            changes.append({"id": row_id, "fields": changed})
    return {
        "off_rows": len(off_ids),
        "on_rows": len(on_ids),
        "same_ids": len(common),
        "added_when_diagnostic_on": sorted(on_ids - off_ids),
        "missing_when_diagnostic_on": sorted(off_ids - on_ids),
        "changed_rows": changes,
        "field_parity": not (off_ids - on_ids or on_ids - off_ids or changes),
    }


def _artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": _hash(path)}


def audit_manifest(manifest_path: str | Path) -> tuple[dict[str, Any], int]:
    source = Path(manifest_path).expanduser().resolve()
    try:
        doc = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read valid UTF-8 JSON manifest: {source}") from exc
    if not isinstance(doc, dict) or set(doc) != {"schema_version", "experiment_id", "dataset_path", "test_context", "runs"}:
        raise AuditError("manifest must contain exactly schema_version, experiment_id, dataset_path, test_context, runs")
    if doc["schema_version"] != 1:
        raise AuditError("schema_version must be 1")
    experiment_id = doc["experiment_id"]
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise AuditError("experiment_id must be non-empty")
    context = _context(doc["test_context"])
    dataset = _resolve(source, doc["dataset_path"], "dataset_path")
    if _hash(dataset) != context["dataset_sha256"]:
        raise AuditError("dataset_path SHA-256 differs from test_context.dataset_sha256")
    runs = doc["runs"]
    if not isinstance(runs, list) or len(runs) != 2:
        raise AuditError("runs must contain exactly diagnostic_off and diagnostic_on")
    roles = {"diagnostic_off", "diagnostic_on"}
    loaded: dict[str, dict[str, Any]] = {}
    run_ids: set[str] = set()
    all_artifact_paths: dict[str, Path] = {}
    artifacts: dict[str, Any] = {}
    blockers: list[str] = []
    raw_context = {key: value for key, value in context.items() if key != "diagnostic_inputs"}
    for index, item in enumerate(runs):
        if not isinstance(item, dict):
            raise AuditError(f"runs[{index}] must be an object")
        required = {"role", "run_id", "observed_context", "input_preset", "tester_report",
                    "tester_log", "signals_csv", "outcomes_csv", "decisions_csv",
                    "deals_csv", "open_positions_csv"}
        if set(item) != required:
            raise AuditError(f"runs[{index}] keys invalid: missing={sorted(required-set(item))}, extra={sorted(set(item)-required)}")
        role = item["role"]
        if role not in roles or role in loaded:
            raise AuditError(f"invalid or duplicate run role {role!r}")
        run_id = item["run_id"]
        if not isinstance(run_id, str) or not run_id.strip() or run_id in run_ids:
            raise AuditError(f"{role}.run_id must be unique and non-empty")
        run_ids.add(run_id)
        observed = item["observed_context"]
        if not isinstance(observed, dict) or set(observed) != set(raw_context):
            raise AuditError(f"{role}.observed_context must repeat common context except diagnostic OFF/ON values")
        for key, expected in raw_context.items():
            actual = observed.get(key)
            if key in {"period_start", "period_end", "locked_oos_start", "locked_oos_end"}:
                equal = _parse_time(actual, f"{role}.observed_context.{key}") == expected
            else:
                equal = actual == expected or (
                    isinstance(expected, float) and not isinstance(actual, bool)
                    and isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=1e-12)
                )
            if not equal:
                raise AuditError(f"{role}.observed_context does not match test_context at {key}")
        path_fields = ("input_preset", "tester_report", "tester_log", "signals_csv",
                       "outcomes_csv", "decisions_csv", "deals_csv", "open_positions_csv")
        paths = {}
        for field in path_fields:
            path = _resolve(source, item[field], f"{role}.{field}", allow_empty=False)
            if field.endswith("_csv"):
                # The export may be header-only to record a legitimate zero-event run.
                if path.stat().st_size == 0:
                    raise AuditError(f"{role}.{field} is empty; use a header-only CSV for zero-row evidence")
            paths[field] = path
            if field != "open_positions_csv":
                canonical = str(path.resolve())
                if canonical in all_artifact_paths:
                    raise AuditError(f"artifact path reused across runs: {path}")
                all_artifact_paths[canonical] = path
        if paths["input_preset"].suffix.lower() != ".set":
            raise AuditError(f"{role}.input_preset must be an actual MT5 .set file")
        if paths["tester_report"].suffix.lower() not in {".html", ".htm"}:
            raise AuditError(f"{role}.tester_report must be an HTML Strategy Tester report")
        log_blockers = _validate_log(paths["tester_log"], context, role)
        blockers.extend(log_blockers)
        tables = {}
        for field, label in (
            ("signals_csv", "signals"), ("outcomes_csv", "outcomes"),
            ("decisions_csv", "decisions"), ("deals_csv", "deals"),
            ("open_positions_csv", "open positions"),
        ):
            header, rows_csv = _read_csv(paths[field], f"{role} {label}")
            tables[field] = {"header": header, "rows": rows_csv}
        loaded[role] = {"run_id": run_id, "paths": paths, "tables": tables}
        artifacts[role] = {field: _artifact(path) for field, path in paths.items()}
    off_paths, on_paths = loaded["diagnostic_off"]["paths"], loaded["diagnostic_on"]["paths"]
    preset_report = _check_preset_pair(off_paths["input_preset"], on_paths["input_preset"], context)

    # Check same CSV schema between OFF and ON before attempting row parity.
    for field in ("signals_csv", "outcomes_csv", "decisions_csv", "deals_csv", "open_positions_csv"):
        a = loaded["diagnostic_off"]["tables"][field]["header"]
        b = loaded["diagnostic_on"]["tables"][field]["header"]
        if a != b:
            raise AuditError(f"{field} headers differ between diagnostic OFF and ON")
    indexed: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
    all_rows: dict[str, Any] = {}
    cost_summary = {}
    for role in ("diagnostic_off", "diagnostic_on"):
        tables = loaded[role]["tables"]
        signals = _validate_signals(tables["signals_csv"]["header"], tables["signals_csv"]["rows"], role)
        outcomes = _validate_outcomes(tables["outcomes_csv"]["header"], tables["outcomes_csv"]["rows"], role)
        decisions = _validate_decisions(tables["decisions_csv"]["header"], tables["decisions_csv"]["rows"], role)
        deals = _validate_deals(tables["deals_csv"]["header"], tables["deals_csv"]["rows"], role)
        open_header = tables["open_positions_csv"]["header"]
        open_rows = tables["open_positions_csv"]["rows"]
        open_key = _field(open_header, "positionid")
        open_ids = [row.get(open_key, "").strip() for row in open_rows]
        if any(not value for value in open_ids) or len(open_ids) != len(set(open_ids)):
            raise AuditError(f"{role} open-position CSV has blank or duplicate position IDs")
        outcome_ids, decision_ids = set(outcomes), set(decisions)
        signal_ids = set(signals)
        unknown_outcomes = sorted(outcome_ids - signal_ids)
        unknown_decisions = sorted(decision_ids - signal_ids)
        missing_decisions = sorted(signal_ids - decision_ids)
        missing_outcomes = sorted(signal_ids - outcome_ids)
        if unknown_outcomes:
            blockers.append(f"{role} has {len(unknown_outcomes)} outcome rows with no source signal")
        if unknown_decisions:
            blockers.append(f"{role} has {len(unknown_decisions)} decision rows with no source signal")
        if missing_decisions:
            blockers.append(f"{role} has {len(missing_decisions)} signals without a final decision record")
        if not signals:
            blockers.append(f"{role} has zero signal rows; diagnostic parity is not performance evidence")
        if not outcomes:
            blockers.append(f"{role} has zero outcome rows")
        if not deals:
            blockers.append(f"{role} has zero deal rows; no cost-inclusive trading result can be measured")
        elif not (deals["commission_cashflow"] <= 0 and deals["swap_cashflow"] <= 0):
            # Positive cashflow can be legitimate rebates/credits, so do not call it invalid.
            pass
        if not signals or not decisions or not outcomes or not deals:
            pass
        event_key = next((name for name in ("eventgroupid", "marketeventid", "eventclusterid") if name in tables["signals_csv"]["header"]), None)
        event_ids = {row.get(event_key, "").strip() for row in signals.values()} - {""} if event_key else set()
        cost_summary[role] = deals
        indexed[role] = {"signals": signals, "outcomes": outcomes, "decisions": decisions}
        all_rows[role] = {
            "signals": len(signals), "outcomes": len(outcomes), "decisions": len(decisions),
            "filled_outcomes": sum(_bool(row["filled"], f"{role} outcome Filled") for row in outcomes.values()),
            "unique_signal_ids": len(signal_ids),
            "independent_event_groups": len(event_ids) if event_key else None,
            "event_independence_status": "measurable_from_exported_group_key" if event_key else "not_measurable_no_event_cluster_id",
            "signals_with_decisions": len(signal_ids & decision_ids),
            "signals_with_outcomes": len(signal_ids & outcome_ids),
            "decision_attribution_coverage_pct": round(100 * len(signal_ids & decision_ids) / len(signal_ids), 4) if signal_ids else None,
            "outcome_attribution_coverage_pct": round(100 * len(signal_ids & outcome_ids) / len(signal_ids), 4) if signal_ids else None,
            "signals_without_decisions": missing_decisions,
            "signals_without_outcomes": missing_outcomes,
            "orphan_decisions": unknown_decisions,
            "orphan_outcomes": unknown_outcomes,
            "cost_ledger": deals,
            "open_position_ids": sorted(open_ids),
        }

    signal_parity = _compare(
        indexed["diagnostic_off"]["signals"], indexed["diagnostic_on"]["signals"],
        ignore_fields=DIAGNOSTIC_FIELDS | VOLATILE_DECISION_FIELDS,
    )
    decision_parity = _compare(
        indexed["diagnostic_off"]["decisions"], indexed["diagnostic_on"]["decisions"],
        ignore_fields=DIAGNOSTIC_FIELDS | VOLATILE_DECISION_FIELDS,
    )
    outcome_parity = _compare(
        indexed["diagnostic_off"]["outcomes"], indexed["diagnostic_on"]["outcomes"],
        ignore_fields=DIAGNOSTIC_FIELDS | VOLATILE_DECISION_FIELDS,
    )
    for name, parity in (("signal", signal_parity), ("decision", decision_parity), ("outcome", outcome_parity)):
        if not parity["field_parity"]:
            blockers.append(f"diagnostic OFF/ON {name} parity differs; inspect added, removed, and changed fields")
    deal_parity = _compare_deal_groups(
        loaded["diagnostic_off"]["tables"]["deals_csv"]["header"],
        loaded["diagnostic_off"]["tables"]["deals_csv"]["rows"],
        loaded["diagnostic_on"]["tables"]["deals_csv"]["header"],
        loaded["diagnostic_on"]["tables"]["deals_csv"]["rows"],
    )
    if not deal_parity["economic_signatures_identical"]:
        blockers.append("diagnostic OFF/ON position economics differ after matching run-local identifiers")
    if not all(item["cost_fields_explicit_and_finite"] for item in cost_summary.values()):
        blockers.append("one or more deal ledgers lack explicit finite commission/swap/fee fields")

    payload = {
        "schema_version": 1,
        "experiment_id": experiment_id.strip(),
        "generated_at_utc": _iso(datetime.now(timezone.utc)),
        "status": "blocked" if blockers else "diagnostic_parity_verified_not_performance_certified",
        "promotion_eligible": False,
        "source_evidence": {
            "dataset": _artifact(dataset),
            "artifacts": artifacts,
            "run_ids": {role: loaded[role]["run_id"] for role in loaded},
        },
        "matched_preset_check": preset_report,
        "run_coverage": all_rows,
        "parity": {
            "signals": signal_parity,
            "decisions": decision_parity,
            "outcomes": outcome_parity,
            "deals": deal_parity,
        },
        "market_data_log_check": {
            "status": "blocked" if any("tester log" in item for item in blockers) else "no_known_synthetic_mode_signature_found",
            "findings": [item for item in blockers if "tester log" in item],
            "limitations": [
                "Negative signatures catch known mathematical/no-history modes but do not prove the data vendor, tick quality, or manifest declarations are truthful.",
                "Inspect each native MT5 report, terminal build, symbol specification, data model, and tick archive before accepting results."
            ],
        },
        "transaction_cost_check": {
            "status": "explicit_cost_fields_present" if all(item["cost_fields_explicit_and_finite"] for item in cost_summary.values()) else "blocked",
            "definition": "Deal net cashflow = sum(profit + signed commission + signed swap + signed broker fee). Historic spread is reflected in real-tick entry/exit prices; incremental spread widening/slippage stress belongs in risk_trailing_experiment.py and must not be charged twice.",
        },
        "blockers": blockers,
        "interpretation": [
            "A zero-trade run is valid evidence of zero trades, but cannot establish profitability or the requested win-rate/return targets.",
            "Unique SignalIDs are not necessarily independent statistical events; independence is measurable only when a real event-cluster key is exported.",
            "This report audits evidence and OFF/ON parity. It does not run MT5, calculate significance, certify performance, submit evidence, or enable execution."
        ],
    }
    return payload, (1 if blockers else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="paired diagnostic OFF/ON MT5 export manifest")
    parser.add_argument("--output", required=True, help="path for the audit JSON report")
    args = parser.parse_args(argv)
    try:
        report, exit_code = audit_manifest(args.manifest)
        target = Path(args.output).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    except (AuditError, OSError, TypeError, ValueError) as exc:
        print(f"audit_mt5_diagnostic_parity: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": report["status"],
        "experiment_id": report["experiment_id"],
        "promotion_eligible": False,
        "blocker_count": len(report["blockers"]),
        "output": str(target),
    }, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
