#!/usr/bin/env python3
"""Compare matched MT5 tests with the experimental trend-regime filter off versus on.

Consumes real Strategy Tester exports and does not invoke MT5. It enforces
identical context and effective .set values except InpRequireTrendingRegime,
requires HTF trailing remain off in both presets, checks explicit deal costs,
hashes artifacts, and reports full-period plus locked-OOS metrics.
It never approves/promotes a strategy.
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
        LedgerError, calculate_metrics, read_deals, read_open_ids, reconstruct_positions,
    )
except ImportError:
    from position_ledger_metrics import (  # type: ignore[no-redef]
        LedgerError, calculate_metrics, read_deals, read_open_ids, reconstruct_positions,
    )

ROLES = ("regime_filter_off", "regime_filter_on")
TOGGLE = "InpRequireTrendingRegime"
HTF_MASTER = "InpDynamicStopUseHTFReferenceLevels"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
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
NUMERIC_KEYS = {"commission_per_lot", "slippage_points", "initial_balance", "risk_percent"}


class MatchedTrailingError(ValueError):
    """Manifest or export cannot support a defensible matched comparison."""


def _parse_time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise MatchedTrailingError(f"{name} must be timezone-aware ISO-8601")
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise MatchedTrailingError(f"{name} is not a valid ISO-8601 timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise MatchedTrailingError(f"{name} must include a timezone")
    return dt.astimezone(timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise MatchedTrailingError(f"cannot read file for hashing: {path}") from exc
    return digest.hexdigest()


def _resolve(base: Path, value: object, name: str, *, allow_empty: bool = False) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise MatchedTrailingError(f"{name} must be a file path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base.parent / path
    path = path.resolve()
    if not path.is_file():
        raise MatchedTrailingError(f"{name} does not exist or is not a file: {path}")
    if not allow_empty and path.stat().st_size == 0:
        raise MatchedTrailingError(f"{name} is empty: {path}")
    return path


def _normalize_context(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MatchedTrailingError(f"{name} must be a JSON object")
    missing, unknown = sorted(CONTEXT_KEYS - set(value)), sorted(set(value) - CONTEXT_KEYS)
    if missing or unknown:
        if missing:
            raise MatchedTrailingError(f"{name} missing keys: {', '.join(missing)}")
        raise MatchedTrailingError(f"{name} has unsupported keys: {', '.join(unknown)}")
    out: dict[str, Any] = {}
    for key in STRING_KEYS:
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            raise MatchedTrailingError(f"{name}.{key} must be a non-empty string")
        out[key] = item.strip()
    out["dataset_sha256"] = out["dataset_sha256"].lower()
    out["ea_source_sha"] = out["ea_source_sha"].lower()
    if not SHA256_RE.fullmatch(out["dataset_sha256"]):
        raise MatchedTrailingError(f"{name}.dataset_sha256 must be a SHA-256 digest")
    if not SOURCE_SHA_RE.fullmatch(out["ea_source_sha"]):
        raise MatchedTrailingError(f"{name}.ea_source_sha must be a commit SHA")
    for key in TIME_KEYS:
        out[key] = _parse_time(value.get(key), f"{name}.{key}")
    if not out["period_start"] < out["locked_oos_start"] < out["locked_oos_end"] <= out["period_end"]:
        raise MatchedTrailingError(f"{name} requires period_start < locked_oos_start < locked_oos_end <= period_end")
    for key in NUMERIC_KEYS:
        raw = value[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(float(raw)):
            raise MatchedTrailingError(f"{name}.{key} must be a finite number")
        out[key] = float(raw)
    if out["commission_per_lot"] < 0 or out["slippage_points"] < 0:
        raise MatchedTrailingError(f"{name} commission and slippage cannot be negative")
    if out["initial_balance"] <= 0 or out["risk_percent"] <= 0:
        raise MatchedTrailingError(f"{name} initial_balance and risk_percent must be positive")
    spread = value["spread_points"]
    if out["spread_model"] not in {"real_ticks", "fixed_points"}:
        raise MatchedTrailingError(f"{name}.spread_model must be real_ticks or fixed_points")
    if spread is not None and (
        isinstance(spread, bool) or not isinstance(spread, (float, int))
        or not math.isfinite(float(spread)) or float(spread) < 0
    ):
        raise MatchedTrailingError(f"{name}.spread_points must be null or finite and non-negative")
    out["spread_points"] = None if spread is None else float(spread)
    if out["spread_model"] == "real_ticks" and out["spread_points"] is not None:
        raise MatchedTrailingError(f"{name}.spread_points must be null with real_ticks")
    if out["spread_model"] == "fixed_points" and (
        out["spread_points"] is None or out["spread_points"] <= 0
    ):
        raise MatchedTrailingError(f"{name} fixed_points requires spread_points > 0")
    return out


def _same_context(left: dict, right: dict, role: str) -> None:
    differences = []
    for key in CONTEXT_KEYS:
        a, b = left[key], right[key]
        equal = a == b
        if isinstance(a, float) and isinstance(b, float):
            equal = math.isclose(a, b, rel_tol=0.0, abs_tol=1e-12)
        if not equal:
            differences.append(key)
    if differences:
        raise MatchedTrailingError(f"{role} context differs from the common run: {', '.join(sorted(differences))}")


def _read_set(path: Path) -> dict[str, str]:
    settings: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise MatchedTrailingError(f"cannot read UTF-8 MT5 .set file: {path}") from exc
    for line_no, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if "=" not in line:
            raise MatchedTrailingError(f"{path.name}:{line_no}: expected NAME=VALUE")
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not name or name in settings:
            raise MatchedTrailingError(f"{path.name}:{line_no}: blank or duplicate setting {name!r}")
        # MT5 .set entries commonly look like value||start||step||stop||N.
        # Compare the effective initial value; the complete file is hashed too.
        settings[name] = raw_value.split("||", 1)[0].strip()
    if not settings:
        raise MatchedTrailingError(f"{path.name} contains no settings")
    return settings


def _bool_setting(settings: dict[str, str], name: str, expected: bool, role: str) -> None:
    raw = settings.get(name)
    if raw is None:
        raise MatchedTrailingError(f"{role} .set is missing required {name}")
    norm = raw.strip().lower()
    accepted = {"true", "1"} if expected else {"false", "0"}
    if norm not in accepted:
        raise MatchedTrailingError(f"{role} requires {name}={'true' if expected else 'false'}, got {raw!r}")


def _require_cost_headers(path: Path) -> None:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        header = next(csv.reader(stream), [])
    canonical = {re.sub(r"[^a-z0-9]", "", item.lower()) for item in header}
    aliases = {
        "commission": {"commission", "dealcommission"},
        "swap": {"swap", "dealswap"},
        "fee": {"fee", "dealfee"},
    }
    missing = [name for name, choices in aliases.items() if not (canonical & choices)]
    if missing:
        raise MatchedTrailingError(
            f"{path.name} must explicitly export commission, swap, and fee columns; missing: {', '.join(missing)}"
        )


def _metrics(positions: list[dict], balance: float) -> dict:
    return calculate_metrics(positions, balance, {})


def _count_censored(positions: list[dict], deals: list[dict], opens: set[str],
                    entry_start: datetime, entry_end: datetime,
                    maturity_cut: datetime) -> dict:
    """Report incomplete and boundary-censored cohorts by entry window."""
    grouped: dict[str, list[dict]] = {}
    for row in deals:
        grouped.setdefault(str(row["position_id"]), []).append(row)
    entry_ids = set()
    for pid, rows in grouped.items():
        entries = [r for r in rows if r["entry"] in {
            "in", "deal_entry_in", "entry_in", "0",
            "inout", "in_out", "deal_entry_inout", "entry_inout", "2",
        }]
        if any(entry_start <= row["time"] < entry_end for row in entries):
            entry_ids.add(pid)
    complete_ids = {
        str(p["position_id"]) for p in positions
        if entry_start <= p["opened_at"] < entry_end and p["closed_at"] < maturity_cut
    }
    closed_after_cut_ids = {
        str(p["position_id"]) for p in positions
        if entry_start <= p["opened_at"] < entry_end and p["closed_at"] >= maturity_cut
    }
    open_ids_in_window = entry_ids & {str(pid) for pid in opens}
    return {
        "positions_listed_open_at_export": len(opens),
        "complete_positions_in_window": len(complete_ids),
        "closed_after_maturity_cut": len(closed_after_cut_ids),
        "opened_positions_still_open_at_export": len(open_ids_in_window),
        "entry_groups_in_window_not_counted_complete": len(entry_ids - complete_ids),
    }


def _load_variant(manifest: dict, manifest_path: Path, raw: dict, context: dict) -> dict:
    role = raw.get("role")
    if role not in ROLES:
        raise MatchedTrailingError(f"variant role must be one of {ROLES}")
    required = {"role", "run_id", "observed_context", "input_preset", "report_path", "deals_csv", "open_positions_csv"}
    if set(raw) != required:
        raise MatchedTrailingError(f"{role} manifest fields must be exactly: {', '.join(sorted(required))}")
    if not isinstance(raw["run_id"], str) or not raw["run_id"].strip():
        raise MatchedTrailingError(f"{role}.run_id must be non-empty")
    observed = _normalize_context(raw["observed_context"], f"{role}.observed_context")
    _same_context(context, observed, role)
    preset = _resolve(manifest_path, raw["input_preset"], f"{role}.input_preset")
    report = _resolve(manifest_path, raw["report_path"], f"{role}.report_path")
    deals_path = _resolve(manifest_path, raw["deals_csv"], f"{role}.deals_csv")
    open_path = _resolve(manifest_path, raw["open_positions_csv"], f"{role}.open_positions_csv")
    if preset.suffix.lower() != ".set":
        raise MatchedTrailingError(f"{role}.input_preset must be .set")
    _require_cost_headers(deals_path)
    settings = _read_set(preset)
    if role == "regime_filter_off":
        _bool_setting(settings, TOGGLE, False, role)
    else:
        _bool_setting(settings, TOGGLE, True, role)
    _bool_setting(settings, HTF_MASTER, False, role)
    try:
        deals = read_deals(deals_path)
        opens = read_open_ids(open_path)
        positions, ignored = reconstruct_positions(deals, opens)
    except (OSError, LedgerError) as exc:
        raise MatchedTrailingError(f"{role} deal-ledger validation failed: {exc}") from exc
    pstart, pend = context["period_start"], context["period_end"]
    ostart, oend = context["locked_oos_start"], context["locked_oos_end"]
    period_entries = [p for p in positions if pstart <= p["opened_at"] < pend and p["closed_at"] < pend]
    oos_entries = [p for p in positions if ostart <= p["opened_at"] < oend and p["closed_at"] < pend]
    censored_period = _count_censored(positions, deals, opens, pstart, pend, pend)
    # The OOS window is defined by entry time; eligible positions can mature
    # through context.period_end. Cross-cut positions remain censored.
    censored_oos = _count_censored(positions, deals, opens, ostart, oend, pend)
    return {
        "role": role,
        "run_id": raw["run_id"],
        "context": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in observed.items()},
        "settings": settings,
        "artifacts": {
            "input_preset": {"path": str(preset), "sha256": _sha256(preset)},
            "tester_report": {"path": str(report), "sha256": _sha256(report)},
            "deals_csv": {"path": str(deals_path), "sha256": _sha256(deals_path)},
            "open_positions_csv": {"path": str(open_path), "sha256": _sha256(open_path)},
        },
        "metrics": {
            "full_period": _metrics(period_entries, context["initial_balance"]),
            "locked_oos": _metrics(oos_entries, context["initial_balance"]),
            "full_period_censoring": censored_period,
            "locked_oos_censoring": censored_oos,
            "ledger_ignored_groups": ignored,
        },
        "_positions": positions,
    }


def _public_variant(data: dict) -> dict:
    return {key: value for key, value in data.items() if key != "_positions"}


def _deltas(off: dict, on: dict) -> dict:
    metric_keys = (
        "completed_positions", "net_pnl", "account_return_pct", "profit_factor",
        "net_expectancy_per_completed_position", "average_win", "average_loss",
        "max_consecutive_losses", "max_closed_position_drawdown_cash",
        "max_closed_position_drawdown_pct",
    )
    out = {}
    for scope in ("full_period", "locked_oos"):
        a, b = off["metrics"][scope], on["metrics"][scope]
        changes = {}
        for key in metric_keys:
            av, bv = a.get(key), b.get(key)
            if isinstance(av, (int, float)) and not isinstance(av, bool) and isinstance(bv, (int, float)) and not isinstance(bv, bool):
                changes[key] = round(bv - av, 8)
            else:
                changes[key] = None
        out[scope] = changes
    return out


def compare_manifest(manifest_path: str | Path) -> dict:
    path = Path(manifest_path).expanduser().resolve()
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MatchedTrailingError(f"cannot read valid JSON manifest: {path}") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "experiment_id", "test_context", "dataset_path", "variants"}:
        raise MatchedTrailingError("manifest must contain exactly schema_version, experiment_id, test_context, dataset_path, variants")
    if manifest["schema_version"] != 1 or not isinstance(manifest["experiment_id"], str) or not manifest["experiment_id"].strip():
        raise MatchedTrailingError("schema_version must be 1 and experiment_id non-empty")
    context = _normalize_context(manifest["test_context"], "test_context")
    dataset = _resolve(path, manifest["dataset_path"], "dataset_path")
    dataset_digest = _sha256(dataset)
    if dataset_digest != context["dataset_sha256"]:
        raise MatchedTrailingError("dataset SHA-256 does not match the actual dataset_path bytes")
    raw_variants = manifest["variants"]
    if not isinstance(raw_variants, list) or len(raw_variants) != 2:
        raise MatchedTrailingError("exactly two variants are required: regime_filter_off and regime_filter_on")
    loaded = {}
    run_ids = set()
    preset_hashes = set()
    for raw in raw_variants:
        if not isinstance(raw, dict):
            raise MatchedTrailingError("each variant must be a JSON object")
        data = _load_variant(manifest, path, raw, context)
        role = data["role"]
        if role in loaded:
            raise MatchedTrailingError(f"duplicate role: {role}")
        if data["run_id"] in run_ids:
            raise MatchedTrailingError("each MT5 run needs a distinct run_id")
        run_ids.add(data["run_id"])
        preset_hash = data["artifacts"]["input_preset"]["sha256"]
        if preset_hash in preset_hashes:
            raise MatchedTrailingError("regime-filter off/on .set files must differ")
        preset_hashes.add(preset_hash)
        loaded[role] = data
    if set(loaded) != set(ROLES):
        raise MatchedTrailingError("both regime_filter_off and regime_filter_on roles are required")
    off, on = loaded["regime_filter_off"], loaded["regime_filter_on"]
    off_settings, on_settings = off["settings"], on["settings"]
    if set(off_settings) != set(on_settings):
        missing_off = sorted(set(on_settings) - set(off_settings))
        missing_on = sorted(set(off_settings) - set(on_settings))
        raise MatchedTrailingError(f".set setting names differ; only_on={missing_off}, only_off={missing_on}")
    differing = sorted(k for k in off_settings if off_settings[k] != on_settings[k])
    if differing != [TOGGLE]:
        raise MatchedTrailingError(
            f"only {TOGGLE} may differ between .set files; differing settings: {differing}"
        )
    if off_settings[TOGGLE].strip().lower() not in {"false", "0"} or on_settings[TOGGLE].strip().lower() not in {"true", "1"}:
        raise MatchedTrailingError("regime filter .set toggles have incorrect effective values")
    # The historical dataset artifact must be the one common to both declared contexts.
    report = {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "comparison_only": True,
        "promotion_recommendation": None,
        "matched_context_verified": True,
        "dataset_digest_verified": True,
        "dataset": {"path": str(dataset), "sha256": dataset_digest},
        "only_effective_set_difference": TOGGLE,
        "variants": {role: _public_variant(data) for role, data in loaded.items()},
        "on_minus_off_deltas": _deltas(off, on),
        "guardrail": "Metrics are calculated from completed positions only and use deal profit + commission + swap + fee. They are not a substitute for native MT5 equity drawdown or stop-modification/restart safety logs; this tool does not run MT5 or approve promotion.",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = compare_manifest(args.manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({
            "output": str(args.output),
            "experiment_id": report["experiment_id"],
            "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            "locked_oos": "reported once when this command is run",
        }, indent=2))
        return 0
    except (MatchedTrailingError, LedgerError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
