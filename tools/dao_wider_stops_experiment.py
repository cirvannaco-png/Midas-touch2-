"""Four-arm matched DaoEA stop-distance experiment from genuine MT5 exports.

This tool validates .set deltas and computes descriptive metrics from closed
position deal exports. It never runs MT5, invents missing trades, or promotes
settings. See docs/DAOEA_WIDER_STOPS_30PCT_EXPERIMENT.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROLES = (
    "A_baseline",
    "B_wider_initial_sl",
    "C_wider_trailing",
    "D_both_wider",
)
BASE_KEYS = {
    "InpAccountRiskProfile",
    "InpSLBufferATR",
    "InpMaxSLDistanceATR",
    "InpDynamicStopATRMult",
    "InpEnableDynamicStop",
}
RISK_SUFFIXES = (
    "RiskPercentPerTrade", "MaxOpenTrades", "MaxDailyLossPercent",
    "MaxDrawdownPercent", "DeriskStartPercent", "DeriskFloor",
    "MaxPortfolioRiskPercent", "MaxPositionsPerSymbol", "MaxPositionsPerGroup",
)
DEAL_COLUMNS = {
    "position_id", "time", "entry", "volume", "profit",
    "commission", "swap", "fee", "risk_cash",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ExperimentError(ValueError):
    """The supplied artifacts cannot support a matched comparison."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stamp(value: str, label: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ExperimentError(f"{label} must be timezone-aware ISO-8601") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ExperimentError(f"{label} must be timezone-aware ISO-8601")
    return dt.astimezone(timezone.utc)


def _setting(value: str) -> str:
    value = value.split("||", 1)[0].strip()
    if value.lower() in {"true", "false"}:
        return value.lower()
    try:
        number = float(value)
    except ValueError:
        return value
    return format(number, ".12g") if math.isfinite(number) else value


def read_set(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ExperimentError(f"cannot read preset: {path}") from exc
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in values:
            raise ExperimentError(f"empty/duplicate input key at {path}:{number}")
        values[key] = _setting(value)
    if not values:
        raise ExperimentError(f"empty MT5 preset: {path}")
    return values


def _risk_key(profile: str, suffix: str) -> str:
    prefix = {"small_account": "InpSmall", "prop_firm": "InpProp"}[profile]
    return prefix + suffix


def _validate_risk_30(preset: dict[str, str], profile: str, role: str) -> None:
    key = _risk_key(profile, "RiskPercentPerTrade")
    try:
        risk = float(preset[key])
    except (KeyError, ValueError) as exc:
        raise ExperimentError(f"{role} missing/nonnumeric {key}") from exc
    if not math.isfinite(risk) or not math.isclose(risk, 30.0, abs_tol=1e-9):
        raise ExperimentError(f"{role} must preserve {key}=30")


def _validate_preset_arms(presets: dict[str, dict[str, str]], profile: str) -> None:
    baseline = presets["A_baseline"]
    missing = BASE_KEYS - set(baseline)
    if missing:
        raise ExperimentError(f"A baseline missing stop keys: {sorted(missing)}")
    selector = {"small_account": "1", "prop_firm": "2"}[profile]
    if baseline.get("InpAccountRiskProfile") != selector:
        raise ExperimentError("InpAccountRiskProfile does not match account profile")
    for role, preset in presets.items():
        if set(preset) != set(baseline):
            raise ExperimentError(f"{role} preset key set differs from A")
        if preset.get("InpAccountRiskProfile") != selector:
            raise ExperimentError(f"{role} account profile differs from test context")
        _validate_risk_30(preset, profile, role)
        if preset.get("InpEnableDynamicStop") != "true":
            raise ExperimentError(f"{role} must keep dynamic trailing enabled")
        # Every risk-related input, including inactive profiles, must match A.
        for key in baseline:
            if ("RiskPercentPerTrade" in key or "MaxOpenTrades" in key
                or "MaxDailyLossPercent" in key or "MaxDrawdownPercent" in key
                or "DeriskStartPercent" in key or "DeriskFloor" in key
                or "MaxPortfolioRiskPercent" in key or "MaxPositionsPerSymbol" in key
                or "MaxPositionsPerGroup" in key):
                if preset[key] != baseline[key]:
                    raise ExperimentError(f"{role} changes risk setting {key}; matched 30% experiment forbids this")
        changed = {key for key in baseline if preset[key] != baseline[key]}
        allowed = {
            "A_baseline": set(),
            "B_wider_initial_sl": {"InpSLBufferATR", "InpMaxSLDistanceATR"},
            "C_wider_trailing": {"InpDynamicStopATRMult"},
            "D_both_wider": {"InpSLBufferATR", "InpMaxSLDistanceATR", "InpDynamicStopATRMult"},
        }[role]
        if changed != allowed:
            raise ExperimentError(f"{role} changed keys {sorted(changed)}; expected exactly {sorted(allowed)}")
    numeric_expectations = {
        "A_baseline": (0.25, 1.50, 1.50),
        "B_wider_initial_sl": (0.3125, 1.875, 1.50),
        "C_wider_trailing": (0.25, 1.50, 1.875),
        "D_both_wider": (0.3125, 1.875, 1.875),
    }
    for role, expected in numeric_expectations.items():
        actual = tuple(float(presets[role][key]) for key in (
            "InpSLBufferATR", "InpMaxSLDistanceATR", "InpDynamicStopATRMult"
        ))
        if any(not math.isclose(a, e, rel_tol=0, abs_tol=1e-9) for a, e in zip(actual, expected)):
            raise ExperimentError(f"{role} stop settings {actual} do not match preregistered values {expected}")


def _read_deals(path: Path, start: datetime, end: datetime) -> tuple[list[dict], int]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not DEAL_COLUMNS <= set(reader.fieldnames):
                raise ExperimentError(f"{path} must contain columns {sorted(DEAL_COLUMNS)}")
            for row in reader:
                pid = (row.get("position_id") or "").strip()
                if not pid:
                    raise ExperimentError(f"{path} has blank position_id")
                try:
                    deal_time = _stamp(row["time"], "deal time")
                    entry_code = row["entry"].strip().lower()
                    volume = float(row["volume"])
                    vals = {k: float(row[k]) for k in ("profit", "commission", "swap", "fee")}
                    risk = float(row["risk_cash"] or 0)
                except (ValueError, TypeError) as exc:
                    raise ExperimentError(f"{path} contains malformed deal values") from exc
                if not all(math.isfinite(v) for v in [volume, risk, *vals.values()]) or volume <= 0 or risk < 0:
                    raise ExperimentError(f"{path} contains non-finite/invalid numeric deal values")
                if entry_code not in {"in", "out", "out_by", "0", "1", "3"}:
                    raise ExperimentError(f"{path} unsupported entry code {entry_code!r}; split inout reversals")
                grouped[pid].append({
                    "time": deal_time, "entry": entry_code, "volume": volume,
                    "net": vals["profit"] + vals["commission"] + vals["swap"] + vals["fee"],
                    "risk": risk,
                })
    except OSError as exc:
        raise ExperimentError(f"cannot read deal CSV: {path}") from exc

    closed: list[dict] = []
    unresolved = 0
    for pid, rows in grouped.items():
        rows.sort(key=lambda r: r["time"])
        entries = [r for r in rows if r["entry"] in {"in", "0"}]
        exits = [r for r in rows if r["entry"] in {"out", "out_by", "1", "3"}]
        if not entries or not exits:
            unresolved += 1
            continue
        first_entry, last_exit = entries[0]["time"], max(r["time"] for r in exits)
        if last_exit < first_entry:
            raise ExperimentError(f"{path} position {pid} exits before entry")
        # Only positions fully contained in the requested window are counted.
        if first_entry < start or last_exit >= end:
            continue
        risk_values = [r["risk"] for r in entries if r["risk"] > 0]
        if not risk_values:
            raise ExperimentError(f"{path} position {pid} has no entry risk_cash")
        if not math.isclose(min(risk_values), max(risk_values), rel_tol=1e-6, abs_tol=1e-8):
            raise ExperimentError(f"{path} position {pid} has inconsistent initial risk_cash")
        pnl = sum(r["net"] for r in rows)
        closed.append({"position_id": pid, "entry_time": first_entry, "exit_time": last_exit,
                       "net_pnl": pnl, "risk_cash": risk_values[0], "realized_r": pnl / risk_values[0]})
    return closed, unresolved


def _metrics(rows: list[dict], initial_balance: float) -> dict:
    pnls = [r["net_pnl"] for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [-p for p in pnls if p < 0]
    gross_profit, gross_loss = sum(wins), sum(losses)
    equity = peak = initial_balance
    max_dd_cash = 0.0
    for row in sorted(rows, key=lambda r: r["exit_time"]):
        equity += row["net_pnl"]
        peak = max(peak, equity)
        max_dd_cash = max(max_dd_cash, peak - equity)
    return {
        "completed_positions": len(rows),
        "net_pnl": round(sum(pnls), 8),
        "net_expectancy_per_position": round(sum(pnls) / len(pnls), 8) if pnls else None,
        "profit_factor": round(gross_profit / gross_loss, 8) if gross_loss else (None if not gross_profit else "infinite"),
        "average_win": round(sum(wins) / len(wins), 8) if wins else None,
        "average_loss_abs": round(sum(losses) / len(losses), 8) if losses else None,
        "mean_realized_r": round(sum(r["realized_r"] for r in rows) / len(rows), 8) if rows else None,
        "max_closed_trade_equity_drawdown_cash": round(max_dd_cash, 8),
        "max_closed_trade_equity_drawdown_pct_of_initial_balance": round(100 * max_dd_cash / initial_balance, 8) if initial_balance else None,
        "consecutive_losses_max": _max_loss_streak(pnls),
        "warning": "Closed-position drawdown omits intratrade equity excursions; use native MT5 equity curve for promotion decisions.",
    }


def _max_loss_streak(pnls: list[float]) -> int:
    current = best = 0
    for pnl in pnls:
        current = current + 1 if pnl < 0 else 0
        best = max(best, current)
    return best


def compare_manifest(manifest_path: str | Path) -> dict:
    path = Path(manifest_path).expanduser().resolve()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentError(f"cannot read manifest JSON: {path}") from exc
    if not isinstance(doc, dict) or set(doc) != {"schema_version", "experiment_id", "test_context", "dataset_path", "variants"}:
        raise ExperimentError("manifest root keys must be schema_version, experiment_id, test_context, dataset_path, variants")
    if doc["schema_version"] != 1 or not isinstance(doc["experiment_id"], str) or not doc["experiment_id"].strip():
        raise ExperimentError("schema_version must be 1 and experiment_id non-empty")
    ctx = doc["test_context"]
    required_ctx = {
        "account_profile", "account_currency", "initial_balance", "symbol", "timeframe",
        "period_start", "period_end", "locked_oos_start", "locked_oos_end",
        "dataset_sha256", "ea_source_sha", "ea_build", "terminal_build", "fill_policy",
        "spread_model", "spread_widening_multiplier", "baseline_spread_points", "cash_per_point_per_lot", "slippage_points", "base_costs_applied_in_tester",
        "stress_costs_applied_in_analysis", "swap_included",
    }
    if not isinstance(ctx, dict) or set(ctx) != required_ctx:
        raise ExperimentError(f"test_context keys must exactly equal {sorted(required_ctx)}")
    profile = ctx["account_profile"]
    if profile not in {"small_account", "prop_firm"}:
        raise ExperimentError("account_profile must be small_account or prop_firm")
    for key in ("account_currency", "symbol", "timeframe", "ea_build", "terminal_build", "fill_policy", "spread_model", "ea_source_sha"):
        if not isinstance(ctx[key], str) or not ctx[key].strip():
            raise ExperimentError(f"test_context.{key} must be non-empty")
    if not isinstance(ctx["initial_balance"], (int, float)) or isinstance(ctx["initial_balance"], bool) or not math.isfinite(ctx["initial_balance"]) or ctx["initial_balance"] <= 0:
        raise ExperimentError("initial_balance must be positive")
    for key in ("period_start", "period_end", "locked_oos_start", "locked_oos_end"):
        ctx[key] = _stamp(ctx[key], f"test_context.{key}")
    if not ctx["period_start"] < ctx["locked_oos_start"] < ctx["locked_oos_end"] <= ctx["period_end"]:
        raise ExperimentError("invalid period/OOS chronological boundaries")
    if not isinstance(ctx["dataset_sha256"], str) or not SHA256_RE.fullmatch(ctx["dataset_sha256"].lower()):
        raise ExperimentError("dataset_sha256 must be a SHA-256 digest")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", ctx["ea_source_sha"].lower()):
        raise ExperimentError("ea_source_sha must be a commit SHA")
    if not isinstance(ctx["spread_widening_multiplier"], (int, float)) or ctx["spread_widening_multiplier"] <= 1:
        raise ExperimentError("spread_widening_multiplier must be > 1")
    for key in ("base_costs_applied_in_tester", "stress_costs_applied_in_analysis", "swap_included"):
        if ctx[key] is not True:
            raise ExperimentError(f"{key} must be true and supported by tester artifacts")
    base = (path.parent / doc["dataset_path"]).resolve()
    if not base.is_file() or _sha256(base) != ctx["dataset_sha256"].lower():
        raise ExperimentError("dataset file missing or SHA-256 does not match manifest")
    variants = doc["variants"]
    if not isinstance(variants, list) or len(variants) != len(ROLES):
        raise ExperimentError(f"variants must contain exactly {len(ROLES)} arms")
    if any(not isinstance(v, dict) or set(v) != {"role", "input_preset", "deals_csv"} for v in variants):
        raise ExperimentError("each variant must contain exactly role, input_preset, deals_csv")
    by_role = {v["role"]: v for v in variants}
    if set(by_role) != set(ROLES):
        raise ExperimentError(f"variant roles must be exactly {ROLES}")
    presets, deal_paths = {}, {}
    for role in ROLES:
        item = by_role[role]
        preset_path = (path.parent / item["input_preset"]).resolve()
        deal_path = (path.parent / item["deals_csv"]).resolve()
        if not preset_path.is_file() or not deal_path.is_file() or deal_path.stat().st_size == 0:
            raise ExperimentError(f"{role} preset/deal artifact missing")
        presets[role] = read_set(preset_path)
        deal_paths[role] = deal_path
    _validate_preset_arms(presets, profile)
    results = {}
    for role in ROLES:
        full, unresolved_full = _read_deals(deal_paths[role], ctx["period_start"], ctx["period_end"])
        oos, unresolved_oos = _read_deals(deal_paths[role], ctx["locked_oos_start"], ctx["locked_oos_end"])
        results[role] = {
            "preset_sha256": _sha256((path.parent / by_role[role]["input_preset"]).resolve()),
            "deals_sha256": _sha256(deal_paths[role]),
            "input_parameters": presets[role],
            "full_period": _metrics(full, float(ctx["initial_balance"])),
            "locked_oos": _metrics(oos, float(ctx["initial_balance"])),
            "unresolved_position_groups_full_period": unresolved_full,
            "unresolved_position_groups_oos": unresolved_oos,
        }
    deltas = {}
    base_metrics = results["A_baseline"]
    for role in ROLES[1:]:
        deltas[role] = {
            "net_pnl_delta_full_period": _delta(results[role]["full_period"]["net_pnl"], base_metrics["full_period"]["net_pnl"]),
            "net_expectancy_delta_full_period": _delta(results[role]["full_period"]["net_expectancy_per_position"], base_metrics["full_period"]["net_expectancy_per_position"]),
            "net_pnl_delta_locked_oos": _delta(results[role]["locked_oos"]["net_pnl"], base_metrics["locked_oos"]["net_pnl"]),
            "net_expectancy_delta_locked_oos": _delta(results[role]["locked_oos"]["net_expectancy_per_position"], base_metrics["locked_oos"]["net_expectancy_per_position"]),
        }
    return {
        "schema_version": 1, "experiment_id": doc["experiment_id"],
        "context": {k: (v.isoformat().replace("+00:00", "Z") if isinstance(v, datetime) else v) for k, v in ctx.items()},
        "variants": results, "candidate_deltas_vs_A": deltas,
        "promotion_recommendation": None,
        "interpretation": "Descriptive comparison only. No candidate is auto-promoted. Require native MT5 equity curves, minimum-volume rejection counts, verified execution-cost assumptions, adequate samples and independent review.",
    }


def _delta(value, baseline):
    if value is None or baseline is None:
        return None
    if isinstance(value, str) or isinstance(baseline, str):
        return None
    return round(value - baseline, 8)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = compare_manifest(args.manifest)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except ExperimentError as exc:
        parser.error(str(exc))
    print(f"Wrote research-only report to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
