#!/usr/bin/env python3
"""Compare matched MT5 Strategy Tester exports without fabricating test results.

This utility validates the run manifest, hashes supplied artifacts, reconstructs
completed positions from genuine deal-history CSVs, and reports full-period plus
locked-OOS metrics for three predeclared strategy variants. It does not run MT5,
parse broker settings out of HTML reports, estimate statistical significance, or
approve a candidate for production.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.position_ledger_metrics import (
        LedgerError,
        calculate_metrics,
        read_deals,
        read_open_ids,
        reconstruct_positions,
    )
except ImportError:
    from position_ledger_metrics import (  # type: ignore[no-redef]
        LedgerError,
        calculate_metrics,
        read_deals,
        read_open_ids,
        reconstruct_positions,
    )


ROLES = ("baseline_dual_lane", "strict_filter_dual_lane", "strict_only")
CONTEXT_KEYS = {
    "symbol", "timeframe", "period_start", "period_end",
    "locked_oos_start", "locked_oos_end", "dataset_sha256",
    "ea_source_sha", "ea_build", "terminal_build", "data_vendor",
    "spread_model", "spread_points", "commission_per_lot",
    "slippage_points", "fill_policy", "initial_balance", "risk_percent",
    "account_currency", "leverage",
}
STRING_KEYS = {
    "symbol", "timeframe", "dataset_sha256", "ea_source_sha", "ea_build",
    "terminal_build", "data_vendor", "spread_model", "fill_policy",
    "account_currency", "leverage",
}
TIME_KEYS = {"period_start", "period_end", "locked_oos_start", "locked_oos_end"}
NUMERIC_KEYS = {
    "commission_per_lot", "slippage_points", "initial_balance", "risk_percent",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
METRIC_KEYS = (
    "completed_positions", "wins", "losses", "breakeven_positions",
    "net_pnl", "account_return_pct", "profit_factor",
    "net_expectancy_per_completed_position",
    "max_closed_position_drawdown_cash", "max_closed_position_drawdown_pct",
    "average_realized_R", "max_consecutive_losses",
)


class ComparisonError(ValueError):
    """Input artifacts cannot support a defensible matched comparison."""


def _parse_time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ComparisonError(f"{name} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ComparisonError(f"{name} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ComparisonError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ComparisonError(f"cannot read artifact for SHA-256: {path}") from exc
    return digest.hexdigest()


def _resolve_file(manifest_path: Path, value: object, name: str, *, allow_empty: bool = False) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ComparisonError(f"{name} must be a file path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = manifest_path.parent / path
    path = path.resolve()
    if not path.is_file():
        raise ComparisonError(f"{name} does not exist or is not a file: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ComparisonError(f"cannot inspect {name}: {path}") from exc
    if not allow_empty and size == 0:
        raise ComparisonError(f"{name} is empty: {path}")
    return path


def _normalize_context(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ComparisonError(f"{name} must be a JSON object")
    unknown = sorted(set(value) - CONTEXT_KEYS)
    missing = sorted(CONTEXT_KEYS - set(value))
    if unknown:
        raise ComparisonError(f"{name} contains unsupported keys: {', '.join(unknown)}")
    if missing:
        raise ComparisonError(f"{name} is missing keys: {', '.join(missing)}")

    normalized: dict[str, Any] = {}
    for key in STRING_KEYS:
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            raise ComparisonError(f"{name}.{key} must be a non-empty string")
        normalized[key] = item.strip()
    normalized["dataset_sha256"] = normalized["dataset_sha256"].lower()
    normalized["ea_source_sha"] = normalized["ea_source_sha"].lower()
    if not SHA256_RE.fullmatch(normalized["dataset_sha256"]):
        raise ComparisonError(f"{name}.dataset_sha256 must be a SHA-256 digest")
    if not SOURCE_SHA_RE.fullmatch(normalized["ea_source_sha"]):
        raise ComparisonError(f"{name}.ea_source_sha must be a 40- or 64-character source commit SHA")

    for key in TIME_KEYS:
        normalized[key] = _parse_time(value.get(key), f"{name}.{key}")
    start = normalized["period_start"]
    end = normalized["period_end"]
    oos_start = normalized["locked_oos_start"]
    oos_end = normalized["locked_oos_end"]
    if not (start < oos_start < oos_end <= end):
        raise ComparisonError(
            f"{name} requires period_start < locked_oos_start < locked_oos_end <= period_end"
        )

    for key in NUMERIC_KEYS:
        raw = value.get(key)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(float(raw)):
            raise ComparisonError(f"{name}.{key} must be a finite number")
        normalized[key] = float(raw)
    if normalized["commission_per_lot"] < 0:
        raise ComparisonError(f"{name}.commission_per_lot cannot be negative")
    if normalized["slippage_points"] < 0:
        raise ComparisonError(f"{name}.slippage_points cannot be negative")
    if normalized["initial_balance"] <= 0 or normalized["risk_percent"] <= 0:
        raise ComparisonError(f"{name}.initial_balance and risk_percent must be positive")

    raw_spread = value.get("spread_points")
    if raw_spread is None:
        normalized["spread_points"] = None
    elif (
        isinstance(raw_spread, bool)
        or not isinstance(raw_spread, (int, float))
        or not math.isfinite(float(raw_spread))
        or float(raw_spread) < 0
    ):
        raise ComparisonError(f"{name}.spread_points must be null or a finite non-negative number")
    else:
        normalized["spread_points"] = float(raw_spread)
    return normalized


def _context_json(context: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (_iso(value) if isinstance(value, datetime) else value)
        for key, value in context.items()
    }


def _require_same_context(expected: dict[str, Any], observed: dict[str, Any], name: str) -> None:
    mismatches = []
    for key in sorted(CONTEXT_KEYS):
        left, right = expected[key], observed[key]
        if isinstance(left, datetime) and isinstance(right, datetime):
            equal = left == right
        elif isinstance(left, float) and isinstance(right, float):
            equal = math.isclose(left, right, rel_tol=0.0, abs_tol=1e-12)
        else:
            equal = left == right
        if not equal:
            mismatches.append(key)
    if mismatches:
        raise ComparisonError(
            f"{name} does not match common test_context for: {', '.join(mismatches)}"
        )


def _read_header(path: Path) -> list[str]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise ComparisonError(f"CSV is missing a header: {path}")
            return [str(item).strip() for item in reader.fieldnames]
    except UnicodeDecodeError as exc:
        raise ComparisonError(f"CSV must be UTF-8: {path}") from exc


def _lane_header_exists(header: list[str]) -> bool:
    aliases = {"lane", "risklane", "entrylane"}
    canonical = {re.sub(r"[^a-z0-9]", "", name.lower()) for name in header}
    return bool(canonical & aliases)


def _metric_delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key in METRIC_KEYS:
        left, right = candidate.get(key), baseline.get(key)
        if isinstance(left, (int, float)) and not isinstance(left, bool) and isinstance(right, (int, float)) and not isinstance(right, bool):
            delta[key] = round(float(left) - float(right), 8)
        else:
            # Profit factor can be the descriptive sentinel "no_losses".
            delta[key] = None
    return delta


def _metrics_for(positions: list[dict[str, Any]], initial_balance: float, ignored: dict[str, int]) -> dict[str, Any]:
    report = calculate_metrics(positions, initial_balance, ignored)
    # Reconstructed datetimes inside equity_curve are already strings, so this
    # payload can be serialized with allow_nan=False without custom encoders.
    return report


def compare_manifest(manifest_path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source_path = Path(manifest_path).expanduser().resolve()
    try:
        manifest = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"cannot read valid UTF-8 JSON manifest: {source_path}") from exc
    if not isinstance(manifest, dict):
        raise ComparisonError("manifest root must be a JSON object")
    allowed_root = {"schema_version", "experiment_id", "test_context", "dataset_path", "variants"}
    unknown = sorted(set(manifest) - allowed_root)
    missing = sorted(allowed_root - set(manifest))
    if unknown:
        raise ComparisonError(f"manifest contains unsupported keys: {', '.join(unknown)}")
    if missing:
        raise ComparisonError(f"manifest is missing keys: {', '.join(missing)}")
    if manifest["schema_version"] != 1:
        raise ComparisonError("schema_version must be 1")
    experiment_id = manifest["experiment_id"]
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ComparisonError("experiment_id must be a non-empty string")

    context = _normalize_context(manifest["test_context"], "test_context")
    dataset_path = _resolve_file(source_path, manifest["dataset_path"], "dataset_path")
    dataset_digest = _sha256(dataset_path)
    if dataset_digest != context["dataset_sha256"]:
        raise ComparisonError("dataset_sha256 does not match the actual dataset_path digest")

    variants = manifest["variants"]
    if not isinstance(variants, list):
        raise ComparisonError("variants must be a JSON array")
    by_role: dict[str, dict[str, Any]] = {}
    run_ids: set[str] = set()
    preset_digests: set[str] = set()
    preset_paths: set[Path] = set()
    report_paths: set[Path] = set()
    deal_paths: set[Path] = set()
    loaded: dict[str, dict[str, Any]] = {}

    allowed_variant = {
        "role", "run_id", "observed_context", "parameters",
        "input_preset", "report_path", "deals_csv", "open_positions_csv",
    }
    for index, raw in enumerate(variants):
        name = f"variants[{index}]"
        if not isinstance(raw, dict):
            raise ComparisonError(f"{name} must be a JSON object")
        unknown = sorted(set(raw) - allowed_variant)
        missing = sorted(allowed_variant - set(raw))
        if unknown:
            raise ComparisonError(f"{name} contains unsupported keys: {', '.join(unknown)}")
        if missing:
            raise ComparisonError(f"{name} is missing keys: {', '.join(missing)}")
        role = raw["role"]
        if role not in ROLES:
            raise ComparisonError(f"{name}.role must be one of: {', '.join(ROLES)}")
        if role in by_role:
            raise ComparisonError(f"duplicate variant role: {role}")
        run_id = raw["run_id"]
        if not isinstance(run_id, str) or not run_id.strip():
            raise ComparisonError(f"{name}.run_id must be a non-empty string")
        run_id = run_id.strip()
        if run_id in run_ids:
            raise ComparisonError(f"duplicate MT5 run_id: {run_id}")
        run_ids.add(run_id)

        observed = _normalize_context(raw["observed_context"], f"{name}.observed_context")
        _require_same_context(context, observed, f"{name}.observed_context")
        parameters = raw["parameters"]
        if not isinstance(parameters, dict) or not parameters:
            raise ComparisonError(f"{name}.parameters must be a non-empty JSON object")
        try:
            # Reject NaN/Infinity and non-JSON values in the human-readable
            # declared parameter snapshot before including it in the report.
            json.dumps(parameters, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ComparisonError(f"{name}.parameters must contain finite JSON values") from exc

        preset_path = _resolve_file(source_path, raw["input_preset"], f"{name}.input_preset")
        report_path = _resolve_file(source_path, raw["report_path"], f"{name}.report_path")
        deals_path = _resolve_file(source_path, raw["deals_csv"], f"{name}.deals_csv")
        open_path = _resolve_file(
            source_path, raw["open_positions_csv"], f"{name}.open_positions_csv", allow_empty=False
        )
        if preset_path in preset_paths:
            raise ComparisonError("each variant must point to a distinct .set input preset file")
        if report_path in report_paths:
            raise ComparisonError("each variant must point to a distinct MT5 report file")
        if deals_path in deal_paths:
            raise ComparisonError("each variant must point to a distinct deal-history CSV")
        preset_paths.add(preset_path)
        report_paths.add(report_path)
        deal_paths.add(deals_path)

        preset_digest = _sha256(preset_path)
        if preset_digest in preset_digests:
            raise ComparisonError("variants have identical input-preset SHA-256 hashes")
        preset_digests.add(preset_digest)
        if not preset_path.suffix.lower() == ".set":
            raise ComparisonError(f"{name}.input_preset must be an MT5 .set file")
        if preset_path.stat().st_size == 0:
            raise ComparisonError(f"{name}.input_preset is empty")
        if not _lane_header_exists(_read_header(deals_path)):
            raise ComparisonError(
                f"{name}.deals_csv needs a lane/risk_lane/entry_lane column for separate lane metrics"
            )

        try:
            try:
                deals = read_deals(deals_path)
            except LedgerError as exc:
                # A header-only deal export is meaningful for a strict-only
                # candidate that generated no executions. Other ledger errors
                # still fail closed.
                if str(exc) == "CSV contains no deal rows":
                    deals = []
                else:
                    raise
            open_ids = read_open_ids(open_path)
            positions, ignored = reconstruct_positions(deals, open_ids)
        except (OSError, LedgerError) as exc:
            raise ComparisonError(f"{name} deal-ledger validation failed: {exc}") from exc

        period_start = context["period_start"]
        period_end = context["period_end"]
        oos_start = context["locked_oos_start"]
        oos_end = context["locked_oos_end"]

        in_period = [p for p in positions if period_start <= p["opened_at"] < period_end]
        period_complete = [p for p in in_period if p["closed_at"] < period_end]
        period_censored = sum(1 for p in in_period if p["closed_at"] >= period_end)
        untagged = [p["position_id"] for p in period_complete if p["lane"] == "UNTAGGED"]
        if untagged:
            raise ComparisonError(
                f"{name} has completed in-period positions without lane attribution: "
                + ", ".join(str(pid) for pid in untagged[:10])
            )

        in_oos = [p for p in positions if oos_start <= p["opened_at"] < oos_end]
        oos_complete = [p for p in in_oos if p["closed_at"] < oos_end]
        oos_censored = sum(1 for p in in_oos if p["closed_at"] >= oos_end)
        untagged_oos = [p["position_id"] for p in oos_complete if p["lane"] == "UNTAGGED"]
        if untagged_oos:
            raise ComparisonError(
                f"{name} has locked-OOS positions without lane attribution: "
                + ", ".join(str(pid) for pid in untagged_oos[:10])
            )

        loaded[role] = {
            "role": role,
            "run_id": run_id,
            "parameters": parameters,
            "artifacts": {
                "input_preset": {"path": str(preset_path.relative_to(source_path.parent)) if preset_path.is_relative_to(source_path.parent) else str(preset_path), "sha256": preset_digest},
                "report": {"path": str(report_path.relative_to(source_path.parent)) if report_path.is_relative_to(source_path.parent) else str(report_path), "sha256": _sha256(report_path)},
                "deals_csv": {"path": str(deals_path.relative_to(source_path.parent)) if deals_path.is_relative_to(source_path.parent) else str(deals_path), "sha256": _sha256(deals_path)},
                "open_positions_csv": {"path": str(open_path.relative_to(source_path.parent)) if open_path.is_relative_to(source_path.parent) else str(open_path), "sha256": _sha256(open_path)},
            },
            "metrics": {
                "full_period": _metrics_for(period_complete, context["initial_balance"], ignored),
                "locked_oos": _metrics_for(oos_complete, context["initial_balance"], ignored),
            },
            "ledger_diagnostics": {
                "deal_rows": len(deals),
                "reconstructed_complete_positions_before_window_filter": len(positions),
                "positions_opened_in_period": len(in_period),
                "period_positions_censored_at_period_end": period_censored,
                "positions_opened_in_locked_oos": len(in_oos),
                "locked_oos_positions_censored_at_oos_end": oos_censored,
                "ignored_groups": ignored,
                "lane_attribution_complete": True,
            },
        }
        by_role[role] = raw

    missing_roles = [role for role in ROLES if role not in loaded]
    if missing_roles:
        raise ComparisonError(f"manifest is missing required variant roles: {', '.join(missing_roles)}")

    baseline = loaded["baseline_dual_lane"]
    comparisons = {}
    for role in ROLES:
        if role == "baseline_dual_lane":
            continue
        comparisons[role] = {
            "versus": "baseline_dual_lane",
            "full_period_delta": _metric_delta(
                loaded[role]["metrics"]["full_period"], baseline["metrics"]["full_period"]
            ),
            "locked_oos_delta": _metric_delta(
                loaded[role]["metrics"]["locked_oos"], baseline["metrics"]["locked_oos"]
            ),
        }

    payload = {
        "status": "comparison_completed" if any(
            loaded[role]["metrics"]["locked_oos"]["completed_positions"] for role in ROLES
        ) else "no_complete_locked_oos_positions",
        "experiment_id": experiment_id.strip(),
        "comparison_only": True,
        "promotion_recommendation": None,
        "promotion_note": (
            "No automatic promotion decision is made. Review evidence sufficiency, "
            "confidence intervals, drawdown limits, regime coverage, and the independent promotion gate."
        ),
        "test_context": _context_json(context),
        "dataset_artifact": {
            "path": str(dataset_path.relative_to(source_path.parent)) if dataset_path.is_relative_to(source_path.parent) else str(dataset_path),
            "sha256": dataset_digest,
        },
        "variants": loaded,
        "candidate_deltas_vs_baseline": comparisons,
    }
    summary = {
        "status": payload["status"],
        "experiment_id": payload["experiment_id"],
        "roles": list(ROLES),
        "source_artifacts_hashed": True,
        "dataset_digest_verified": True,
        "matched_context_verified": True,
        "no_mt5_run_performed_by_this_tool": True,
        "no_statistical_significance_claimed": True,
        "promotion_recommendation": None,
    }
    return payload, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="JSON manifest with matched tester runs and exact artifacts")
    parser.add_argument("--output", required=True, help="Path for the comparison JSON report")
    args = parser.parse_args()
    try:
        payload, summary = compare_manifest(args.manifest)
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        summary["output_file"] = str(output_path)
        summary["comparison_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest()
    except (ComparisonError, OSError, TypeError, ValueError) as exc:
        print(f"compare_mt5_variant_runs: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
