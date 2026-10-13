#!/usr/bin/env python3
"""Score the registered MT5 locked-OOS pair once, with cost stress and Monte Carlo.

The one-shot lock is created atomically before any performance report is emitted.
A failed evaluation still consumes that workspace lock: inspect the failure and
fix tooling or artifacts without rerunning on this OOS interval. This is a
workspace/file-system guard, not a central server-side enforcement mechanism;
keep the lock and output in immutable/versioned storage.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.compare_htf_trailing_runs import (
        MatchedTrailingError, ROLES, TOGGLE, WEEKLY, MONTHLY,
        _normalize_context, _resolve, _read_set, _same_context,
        _bool_setting, _require_cost_headers, _sha256, compare_manifest,
    )
    from tools.position_ledger_metrics import IN, INOUT, LedgerError, read_deals, read_open_ids, reconstruct_positions
    from tools.cost_stress_monte_carlo import (
        CostStressError, incremental_cost_for_position, performance_metrics, monte_carlo_drawdown,
        _walk_forward_folds,
    )
except ImportError:
    from compare_htf_trailing_runs import (
        MatchedTrailingError, ROLES, TOGGLE, WEEKLY, MONTHLY,
        _normalize_context, _resolve, _read_set, _same_context,
        _bool_setting, _require_cost_headers, _sha256, compare_manifest,
    )
    from position_ledger_metrics import IN, INOUT, LedgerError, read_deals, read_open_ids, reconstruct_positions
    from cost_stress_monte_carlo import (
        CostStressError, incremental_cost_for_position, performance_metrics, monte_carlo_drawdown,
        _walk_forward_folds,
    )


class LockedOOSGateError(ValueError):
    """Locked-OOS preflight or single-use constraints failed."""


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LockedOOSGateError(f"cannot read valid JSON {label}: {path}") from exc
    if not isinstance(value, dict):
        raise LockedOOSGateError(f"{label} must contain a JSON object")
    return value


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _parse_time(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise LockedOOSGateError(f"{label} must be timezone-aware ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise LockedOOSGateError(f"{label} is not a valid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LockedOOSGateError(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _preflight(reservation_path: Path, manifest_path: Path, freeze_path: Path,
               *, attest_untouched: bool) -> dict[str, Any]:
    reservation = _load_json(reservation_path, "OOS reservation")
    manifest = _load_json(manifest_path, "matched trailing manifest")
    freeze = _load_json(freeze_path, "frozen configuration manifest")

    required_reservation = {
        "schema_version", "reservation_id", "status", "locked_oos_start",
        "locked_oos_end", "maturity_end", "external_freshness_attestation_required",
    }
    if set(reservation) != required_reservation:
        raise LockedOOSGateError("reservation file has missing or unsupported fields")
    if reservation["schema_version"] != 1 or reservation["status"] != "reserved_unscored":
        raise LockedOOSGateError("OOS reservation is not in reserved_unscored state")
    if reservation["external_freshness_attestation_required"] is not True or not attest_untouched:
        raise LockedOOSGateError("explicit --attest-untouched is required; repository history cannot prove external freshness")

    if set(manifest) != {"schema_version", "experiment_id", "test_context", "dataset_path", "variants"}:
        raise LockedOOSGateError("matched manifest has missing or unsupported fields")
    if manifest["schema_version"] != 1 or not isinstance(manifest["experiment_id"], str) or not manifest["experiment_id"].strip():
        raise LockedOOSGateError("matched manifest schema or experiment_id is invalid")
    context = _normalize_context(manifest["test_context"], "test_context")
    oos_start = _parse_time(reservation["locked_oos_start"], "reservation.locked_oos_start")
    oos_end = _parse_time(reservation["locked_oos_end"], "reservation.locked_oos_end")
    maturity = _parse_time(reservation["maturity_end"], "reservation.maturity_end")
    if context["locked_oos_start"] != oos_start or context["locked_oos_end"] != oos_end:
        raise LockedOOSGateError("matched manifest OOS dates do not equal the registered reservation")
    if context["period_end"] < maturity or not oos_start < oos_end <= maturity:
        raise LockedOOSGateError("test period must include the registered OOS interval and its maturity cut")

    required_freeze = {
        "schema_version", "experiment_id", "frozen_at", "matched_manifest_sha256",
        "point_value_per_lot", "spread_widening_points", "slippage_points_per_fill",
        "simulations", "seed", "train_months", "test_months", "folds",
        "promotion_criteria", "oos_previously_inspected",
    }
    if set(freeze) != required_freeze:
        raise LockedOOSGateError("frozen config file has missing or unsupported fields")
    if freeze["schema_version"] != 1 or freeze["experiment_id"] != manifest["experiment_id"]:
        raise LockedOOSGateError("frozen config schema/experiment_id does not match the matched manifest")
    _parse_time(freeze["frozen_at"], "frozen_config.frozen_at")
    if freeze["matched_manifest_sha256"] != _digest(manifest_path):
        raise LockedOOSGateError("matched manifest changed after the research configuration was frozen")
    if freeze["oos_previously_inspected"] is not False:
        raise LockedOOSGateError("frozen config must attest that this interval was not previously inspected")
    if isinstance(freeze["point_value_per_lot"], bool) or not isinstance(freeze["point_value_per_lot"], (int, float)) or not math.isfinite(float(freeze["point_value_per_lot"])) or float(freeze["point_value_per_lot"]) <= 0:
        raise LockedOOSGateError("point_value_per_lot must be the confirmed positive account-currency point value for one lot")
    for key in ("spread_widening_points", "slippage_points_per_fill"):
        values = freeze[key]
        if not isinstance(values, list) or not values or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or v < 0 for v in values):
            raise LockedOOSGateError(f"{key} must be a non-empty list of finite non-negative numbers")
    if isinstance(freeze["simulations"], bool) or not isinstance(freeze["simulations"], int) or freeze["simulations"] < 100:
        raise LockedOOSGateError("simulations must be an integer >= 100")
    if isinstance(freeze["seed"], bool) or not isinstance(freeze["seed"], int):
        raise LockedOOSGateError("seed must be an integer")
    for key in ("train_months", "test_months", "folds"):
        if isinstance(freeze[key], bool) or not isinstance(freeze[key], int) or freeze[key] <= 0:
            raise LockedOOSGateError(f"{key} must be a positive integer")
    if not isinstance(freeze["promotion_criteria"], list) or not freeze["promotion_criteria"] or any(not isinstance(v, str) or not v.strip() for v in freeze["promotion_criteria"]):
        raise LockedOOSGateError("promotion_criteria must be a non-empty list of human-readable frozen thresholds")

    # Check artifact existence, hash the common dataset, validate cost headers,
    # and check the only allowable preset difference without calculating returns.
    dataset = _resolve(manifest_path, manifest["dataset_path"], "dataset_path")
    if _sha256(dataset) != context["dataset_sha256"]:
        raise LockedOOSGateError("actual dataset hash does not match the frozen context")
    variants = manifest["variants"]
    if not isinstance(variants, list) or len(variants) != 2:
        raise LockedOOSGateError("exactly two matched variants are required")
    loaded: dict[str, dict] = {}
    for raw in variants:
        if not isinstance(raw, dict):
            raise LockedOOSGateError("each variant must be an object")
        role = raw.get("role")
        if role not in ROLES or role in loaded:
            raise LockedOOSGateError("variant roles must be unique htf_trailing_off and htf_trailing_on")
        required_fields = {"role", "run_id", "observed_context", "input_preset", "report_path", "deals_csv", "open_positions_csv"}
        if set(raw) != required_fields:
            raise LockedOOSGateError(f"{role} contains missing or unsupported manifest fields")
        observed = _normalize_context(raw["observed_context"], f"{role}.observed_context")
        _same_context(context, observed, role)
        preset = _resolve(manifest_path, raw["input_preset"], f"{role}.input_preset")
        report = _resolve(manifest_path, raw["report_path"], f"{role}.report_path")
        deals = _resolve(manifest_path, raw["deals_csv"], f"{role}.deals_csv")
        opens = _resolve(manifest_path, raw["open_positions_csv"], f"{role}.open_positions_csv")
        if preset.suffix.lower() != ".set":
            raise LockedOOSGateError(f"{role} input preset must be a .set file")
        _require_cost_headers(deals)
        with opens.open("r", newline="", encoding="utf-8-sig") as stream:
            if not next(csv.reader(stream), []):
                raise LockedOOSGateError(f"{role} open-position CSV must have a header")
        settings = _read_set(preset)
        _bool_setting(settings, TOGGLE, role == "htf_trailing_on", role)
        _bool_setting(settings, WEEKLY, True, role)
        _bool_setting(settings, MONTHLY, True, role)
        loaded[role] = {"settings": settings, "preset": preset, "report": report, "deals": deals, "opens": opens}

    off, on = loaded["htf_trailing_off"], loaded["htf_trailing_on"]
    if set(off["settings"]) != set(on["settings"]):
        raise LockedOOSGateError("preset setting names differ between matched variants")
    differences = sorted(k for k in off["settings"] if off["settings"][k] != on["settings"][k])
    if differences != [TOGGLE]:
        raise LockedOOSGateError(f"only {TOGGLE} may differ; found {differences}")
    if freeze["point_value_per_lot"] <= 0:
        raise LockedOOSGateError("invalid point value")
    if _digest(manifest_path) != freeze["matched_manifest_sha256"]:
        raise LockedOOSGateError("manifest hash recheck failed")
    return {
        "reservation": reservation,
        "manifest": manifest,
        "context": context,
        "freeze": freeze,
        "dataset": dataset,
        "variants": loaded,
        "manifest_sha256": _digest(manifest_path),
        "freeze_sha256": _digest(freeze_path),
        "dataset_sha256": _digest(dataset),
    }


def _segment_positions(variant: dict, start: datetime, end: datetime) -> tuple[list[dict], dict]:
    deals = read_deals(variant["deals"])
    opens = read_open_ids(variant["opens"])
    positions, ignored = reconstruct_positions(deals, opens)
    eligible = [p for p in positions if start <= p["opened_at"] < end and p["closed_at"] < end]
    deals_by_id: dict[str, list[dict]] = {}
    for deal in deals:
        deals_by_id.setdefault(str(deal["position_id"]), []).append(deal)
    for position in eligible:
        position["turnover_volume"] = sum(float(d["volume"]) for d in deals_by_id[position["position_id"]])
    entry_ids = set()
    for pid, rows in deals_by_id.items():
        entries = [row for row in rows if row["entry"] in IN or row["entry"] in INOUT]
        if any(start <= row["time"] < end for row in entries):
            entry_ids.add(pid)
    eligible_ids = {str(p["position_id"]) for p in eligible}
    late_close_ids = {
        str(p["position_id"]) for p in positions
        if start <= p["opened_at"] < end and p["closed_at"] >= end
    }
    return eligible, {
        "completed_positions": len(eligible),
        "closed_after_segment_boundary": len(late_close_ids),
        "opened_but_not_completed": len(entry_ids - eligible_ids),
        "listed_open_positions_at_export": len(opens),
        "ledger_ignored_groups": ignored,
    }


def _scenario_grid(rows: list[dict], *, point_value: float, initial_balance: float,
                   spreads: list[float], slippages: list[float], simulations: int,
                   seed: int) -> list[dict]:
    output = []
    for spread in sorted(set(float(v) for v in spreads)):
        for slip in sorted(set(float(v) for v in slippages)):
            pnls = [
                p["net_pnl"] - incremental_cost_for_position(
                    p["turnover_volume"], point_value, spread, slip
                ) for p in rows
            ]
            scenario = {
                "incremental_spread_widening_points": spread,
                "extra_slippage_points_per_fill": slip,
                "incremental_stress_cost": round(sum(p["net_pnl"] - net for p, net in zip(rows, pnls)), 8),
                "metrics": performance_metrics(pnls, initial_balance),
                "monte_carlo": monte_carlo_drawdown(pnls, initial_balance, simulations, seed),
            }
            output.append(scenario)
    return output


def evaluate_once(reservation_path: Path, manifest_path: Path, freeze_path: Path,
                  lock_path: Path, output_path: Path, *, attest_untouched: bool) -> dict:
    info = _preflight(reservation_path, manifest_path, freeze_path, attest_untouched=attest_untouched)
    lock_path = lock_path.expanduser().resolve()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    lock_record = {
        "schema_version": 1,
        "status": "consumed_evaluation_started",
        "reservation_id": info["reservation"]["reservation_id"],
        "experiment_id": info["manifest"]["experiment_id"],
        "evaluated_at": now.isoformat(),
        "attestation": "operator explicitly asserted the registered interval is untouched before this one-shot evaluation",
        "matched_manifest_sha256": info["manifest_sha256"],
        "frozen_config_sha256": info["freeze_sha256"],
        "dataset_sha256": info["dataset_sha256"],
    }
    try:
        fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise LockedOOSGateError(f"locked OOS has already been consumed in this workspace: {lock_path}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(lock_record, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())

    try:
        # All results from the locked interval are produced in this single call;
        # never rerun on the same window after reading them.
        matched = compare_manifest(manifest_path)
        context, freeze = info["context"], info["freeze"]
        dev_start = context["period_start"]
        oos_start = context["locked_oos_start"]
        oos_end = context["locked_oos_end"]
        maturity = _parse_time(info["reservation"]["maturity_end"], "reservation.maturity_end")
        comparison = {
            "matched_context_verified": matched["matched_context_verified"],
            "dataset_digest_verified": matched["dataset_digest_verified"],
            "dataset": matched["dataset"],
            "only_effective_set_difference": matched["only_effective_set_difference"],
            "variants": {},
            "locked_oos_on_minus_off_delta": matched["on_minus_off_deltas"]["locked_oos"],
        }
        stress: dict[str, Any] = {}
        for role, variant in info["variants"].items():
            dev_rows, dev_counts = _segment_positions(variant, dev_start, oos_start)
            oos_rows, oos_counts = _segment_positions(variant, oos_start, oos_end)
            role_compare = matched["variants"][role]
            comparison["variants"][role] = {
                "run_id": role_compare["run_id"],
                "artifacts": role_compare["artifacts"],
                "locked_oos_cost_inclusive_metrics": role_compare["metrics"]["locked_oos"],
                "locked_oos_censoring": role_compare["metrics"]["locked_oos_censoring"],
            }
            stress[role] = {
                "development": {
                    "start": dev_start.isoformat(), "end": oos_start.isoformat(),
                    "counts": dev_counts,
                    "cost_stress_monte_carlo": _scenario_grid(
                        dev_rows, point_value=float(freeze["point_value_per_lot"]),
                        initial_balance=float(context["initial_balance"]),
                        spreads=freeze["spread_widening_points"],
                        slippages=freeze["slippage_points_per_fill"],
                        simulations=freeze["simulations"], seed=int(freeze["seed"]),
                    ),
                    "fixed_configuration_walk_forward": {},
                },
                "locked_oos": {
                    "start": oos_start.isoformat(), "end": oos_end.isoformat(),
                    "maturity_cut": maturity.isoformat(),
                    "counts": oos_counts,
                    "cost_stress_monte_carlo": _scenario_grid(
                        oos_rows, point_value=float(freeze["point_value_per_lot"]),
                        initial_balance=float(context["initial_balance"]),
                        spreads=freeze["spread_widening_points"],
                        slippages=freeze["slippage_points_per_fill"],
                        simulations=freeze["simulations"], seed=int(freeze["seed"]),
                    ),
                },
            }
            # This is a fixed-parameter chronological stability report, not an optimizer.
            for spread in sorted(set(float(v) for v in freeze["spread_widening_points"])):
                for slip in sorted(set(float(v) for v in freeze["slippage_points_per_fill"])):
                    key = f"spread_plus_{spread}_slippage_plus_{slip}"
                    stress[role]["development"]["fixed_configuration_walk_forward"][key] = _walk_forward_folds(
                        dev_rows, dev_start, oos_start,
                        int(freeze["train_months"]), int(freeze["test_months"]), int(freeze["folds"]),
                        spread, slip, float(freeze["point_value_per_lot"]), float(context["initial_balance"]),
                    )

        output = {
            "schema_version": 1,
            "experiment_id": info["manifest"]["experiment_id"],
            "decision": "evaluation_only_no_promotion_or_live_deployment",
            "one_shot": {
                "reservation_id": info["reservation"]["reservation_id"],
                "consumption_lock": str(lock_path),
                "evaluated_at": now.isoformat(),
                "reservation_interval": {
                    "start": oos_start.isoformat(),
                    "end": oos_end.isoformat(),
                    "maturity_cut": maturity.isoformat(),
                },
                "manifest_sha256": info["manifest_sha256"],
                "frozen_config_sha256": info["freeze_sha256"],
                "operator_untouched_attestation_required_and_received": True,
            },
            "matched_htf_trailing_comparison": comparison,
            "predeclared_cost_stress_and_monte_carlo": stress,
            "limitations": [
                "The actual MT5 deal export is authoritative for realized profit, commission, swap and fee; incremental spread/slippage stresses are layered on top and must be calibrated to recorded broker conditions.",
                "Monte Carlo trade-order shuffle estimates sequence risk for the observed outcomes; bootstrap estimates sampling uncertainty. Neither predicts future returns or replaces native MT5 tick-level equity drawdown.",
                "The walk-forward section evaluates the fixed configuration across chronological folds; it does not fit parameters on each training fold.",
                "A successful script run, CI, or compile is not proof of profitability or live-readiness.",
            ],
        }
        output_path = output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        lock_record["status"] = "consumed_evaluation_complete"
        lock_record["report_path"] = str(output_path)
        lock_record["report_sha256"] = _digest(output_path)
        lock_record["finished_at"] = datetime.now(timezone.utc).isoformat()
        lock_path.write_text(json.dumps(lock_record, indent=2) + "\n", encoding="utf-8")
        return {
            "status": lock_record["status"],
            "output": str(output_path),
            "output_sha256": lock_record["report_sha256"],
            "consumption_lock": str(lock_path),
            "locked_oos_entries": oos_counts if stress else None,
        }
    except Exception as exc:
        lock_record["status"] = "consumed_evaluation_failed"
        lock_record["failure_type"] = type(exc).__name__
        lock_record["failure_message"] = str(exc)[:500]
        lock_record["finished_at"] = datetime.now(timezone.utc).isoformat()
        lock_path.write_text(json.dumps(lock_record, indent=2) + "\n", encoding="utf-8")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reservation", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--frozen-config", required=True, type=Path)
    parser.add_argument("--consumption-lock", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--attest-untouched", action="store_true", help="assert the interval has not been inspected or used for tuning outside this repo")
    args = parser.parse_args()
    try:
        result = evaluate_once(
            args.reservation, args.manifest, args.frozen_config,
            args.consumption_lock, args.output, attest_untouched=args.attest_untouched,
        )
        print(json.dumps(result, indent=2))
        return 0
    except (LockedOOSGateError, MatchedTrailingError, CostStressError, LedgerError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
