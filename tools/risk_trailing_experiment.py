"""Auditable five-arm stop/risk comparison from real MT5 Strategy Tester exports.

The comparator does not run MT5, infer missing trades, or promote settings.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROLES = (
    "A_current_baseline", "B_trailing_off", "C_trailing_candidate",
    "D_tight_risk", "E_calibrated_risk",
)
RISK_KEYS = {
    "InpRiskPercentPerTrade", "InpMaxOpenTrades", "InpMaxDailyLossPercent",
    "InpMaxDrawdownPercent", "InpDeriskStartPercent", "InpDeriskFloor",
    "InpMaxPortfolioRiskPercent", "InpMaxPositionsPerSymbol", "InpMaxPositionsPerGroup",
}
TRAILING_KEYS = {
    "InpEnableDynamicStop", "InpDynamicStopActivateAtR", "InpDynamicStopBreakevenAtR",
    "InpDynamicStopATRMult", "InpDynamicStopMinImprovementPoints",
    "InpDynamicStopMaxSpreadPoints", "InpDynamicStopMinATR", "InpDynamicStopMaxATR",
    "InpDynamicStopModifyIntervalSec", "InpDynamicStopUseStructuralAnchor",
    "InpDynamicStopStructuralBufferATR", "InpBreakEvenAtR", "InpPartialAtR",
    "InpPartialFraction", "InpTrailATRMult",
}
COST_KEYS = {"InpSimCommissionPerLot", "InpSimSpreadPoints", "InpSimSlippagePoints"}
CONTEXT_KEYS = {
    "account_profile", "symbol", "timeframe", "period_start", "period_end",
    "locked_oos_start", "locked_oos_end", "dataset_sha256", "ea_source_sha",
    "ea_build", "terminal_build", "data_vendor", "spread_model",
    "spread_widening_multiplier", "spread_points", "commission_per_lot",
    "slippage_points", "swap_included", "fill_policy", "costs_applied_in_tester",
    "initial_balance", "account_currency", "leverage",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class ExperimentError(ValueError):
    """Inputs cannot support a defensible matched comparison."""


def _time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentError(f"{name} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExperimentError(f"{name} is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExperimentError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError as exc:
        raise ExperimentError(f"cannot read artifact: {path}") from exc
    return h.hexdigest()


def _file(base: Path, value: object, name: str, allow_empty: bool = False) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentError(f"{name} must be a file path")
    result = Path(value).expanduser()
    if not result.is_absolute():
        result = base.parent / result
    result = result.resolve()
    if not result.is_file() or (not allow_empty and result.stat().st_size == 0):
        raise ExperimentError(f"{name} is missing, not a file, or empty: {result}")
    return result


def _num(value: object, name: str, *, positive: bool = False, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ExperimentError(f"{name} must be a finite number")
    result = float(value)
    if positive and result <= 0:
        raise ExperimentError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise ExperimentError(f"{name} must be at least {minimum}")
    return result


def _context(raw: object, name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ExperimentError(f"{name} must be an object")
    missing, extra = sorted(CONTEXT_KEYS - set(raw)), sorted(set(raw) - CONTEXT_KEYS)
    if missing or extra:
        raise ExperimentError(f"{name} context keys invalid: missing={missing}, extra={extra}")
    result: dict[str, Any] = {}
    string_keys = (
        "account_profile", "symbol", "timeframe", "ea_build", "terminal_build",
        "data_vendor", "spread_model", "fill_policy", "account_currency", "leverage",
    )
    for key in string_keys:
        value = raw[key]
        if not isinstance(value, str) or not value.strip():
            raise ExperimentError(f"{name}.{key} must be a non-empty string")
        result[key] = value.strip()
    if result["account_profile"] not in {"small_account", "prop_firm"}:
        raise ExperimentError(f"{name}.account_profile must be small_account or prop_firm")
    for key in ("period_start", "period_end", "locked_oos_start", "locked_oos_end"):
        result[key] = _time(raw[key], f"{name}.{key}")
    if not result["period_start"] < result["locked_oos_start"] < result["locked_oos_end"] <= result["period_end"]:
        raise ExperimentError(f"{name} requires period_start < locked_oos_start < locked_oos_end <= period_end")
    result["dataset_sha256"] = str(raw["dataset_sha256"]).lower()
    result["ea_source_sha"] = str(raw["ea_source_sha"]).lower()
    if not SHA256_RE.fullmatch(result["dataset_sha256"]):
        raise ExperimentError(f"{name}.dataset_sha256 must be a SHA-256 digest")
    if not SOURCE_SHA_RE.fullmatch(result["ea_source_sha"]):
        raise ExperimentError(f"{name}.ea_source_sha must be a 40- or 64-character commit SHA")
    result["spread_widening_multiplier"] = _num(raw["spread_widening_multiplier"], f"{name}.spread_widening_multiplier", minimum=1.01)
    result["commission_per_lot"] = _num(raw["commission_per_lot"], f"{name}.commission_per_lot", positive=True)
    result["slippage_points"] = _num(raw["slippage_points"], f"{name}.slippage_points", positive=True)
    result["initial_balance"] = _num(raw["initial_balance"], f"{name}.initial_balance", positive=True)
    result["spread_points"] = None if raw["spread_points"] is None else _num(raw["spread_points"], f"{name}.spread_points", minimum=0)
    for key in ("swap_included", "costs_applied_in_tester"):
        if not isinstance(raw[key], bool) or not raw[key]:
            raise ExperimentError(f"{name}.{key} must be true; costs and swap must be applied in the tester")
        result[key] = raw[key]
    if result["spread_model"] not in {"real_ticks_plus_stress", "variable_spread_stress"}:
        raise ExperimentError(f"{name}.spread_model must explicitly include variable-spread/widening stress")
    if result["spread_model"] == "variable_spread_stress" and result["spread_points"] is None:
        raise ExperimentError(f"{name}.spread_points is required for variable_spread_stress")
    return result


def _setting(value: str) -> str:
    value = value.split("||", 1)[0].strip()
    if value.lower() in {"true", "false"}:
        return value.lower()
    try:
        number = float(value)
    except ValueError:
        return value
    return format(number, ".12g") if math.isfinite(number) else value


def _preset(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ExperimentError(f"cannot read .set file: {path}") from exc
    for line_no, line in enumerate(lines, 1):
        row = line.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        key = key.strip()
        if not key or key in values:
            raise ExperimentError(f"empty or duplicate preset key at {path}:{line_no}")
        values[key] = _setting(value)
    if not values:
        raise ExperimentError(f"empty MT5 input preset: {path}")
    return values


def _float_setting(p: dict[str, str], key: str, role: str) -> float:
    try:
        value = float(p[key])
    except (KeyError, ValueError) as exc:
        raise ExperimentError(f"{role}.{key} must be numeric") from exc
    if not math.isfinite(value):
        raise ExperimentError(f"{role}.{key} must be finite")
    return value


def _bool_setting(p: dict[str, str], key: str, role: str) -> bool:
    value = p.get(key, "").lower()
    if value not in {"true", "false"}:
        raise ExperimentError(f"{role}.{key} must be true/false")
    return value == "true"


def _validate_presets(presets: dict[str, dict[str, str]]) -> None:
    base = presets["A_current_baseline"]
    for role, p in presets.items():
        if set(p) != set(base):
            raise ExperimentError(f"{role} preset key set differs from A")
        for group, name in ((RISK_KEYS, "risk"), (TRAILING_KEYS, "trailing"), (COST_KEYS, "cost")):
            missing = group - set(p)
            if missing:
                raise ExperimentError(f"{role} preset missing {name} settings: {sorted(missing)}")
        if any(p[k] != base[k] for k in COST_KEYS):
            raise ExperimentError("execution-cost inputs must remain identical in every arm")
        for key in COST_KEYS:
            if _float_setting(p, key, role) <= 0:
                raise ExperimentError(f"{role}.{key} must be positive")

    non_policy = set(base) - RISK_KEYS - TRAILING_KEYS
    for role, p in presets.items():
        changed = sorted(k for k in non_policy if p[k] != base[k])
        if changed:
            raise ExperimentError(f"{role} changes non-risk/trailing settings versus A: {', '.join(changed)}")
    for role in ("A_current_baseline", "B_trailing_off", "C_trailing_candidate"):
        if any(presets[role][k] != base[k] for k in RISK_KEYS):
            raise ExperimentError(f"{role} must use A's identical risk settings")

    if not _bool_setting(base, "InpEnableDynamicStop", "A"):
        raise ExperimentError("A baseline must have trailing stop enabled")
    b = presets["B_trailing_off"]
    if _bool_setting(b, "InpEnableDynamicStop", "B"):
        raise ExperimentError("B must set InpEnableDynamicStop=false")
    if {k for k in base if b[k] != base[k]} != {"InpEnableDynamicStop"}:
        raise ExperimentError("B may differ from A only by InpEnableDynamicStop=false")
    c = presets["C_trailing_candidate"]
    if not _bool_setting(c, "InpEnableDynamicStop", "C"):
        raise ExperimentError("C must keep trailing enabled")
    c_changed = {k for k in base if c[k] != base[k]}
    if not c_changed or not c_changed <= TRAILING_KEYS or c_changed == {"InpEnableDynamicStop"}:
        raise ExperimentError("C must vary at least one trailing parameter other than the enable toggle")

    tight = {
        "InpRiskPercentPerTrade": "0.35", "InpMaxOpenTrades": "2",
        "InpMaxDailyLossPercent": "2", "InpMaxDrawdownPercent": "8",
        "InpDeriskStartPercent": "3", "InpDeriskFloor": "0.15",
        "InpMaxPortfolioRiskPercent": "1.5", "InpMaxPositionsPerSymbol": "2",
        "InpMaxPositionsPerGroup": "2",
    }
    d = presets["D_tight_risk"]
    if any(d[k] != v for k, v in tight.items()):
        raise ExperimentError("D_tight_risk must use the predeclared tighter-risk candidate")
    changed_d = {k for k in base if d[k] != base[k]}
    if not changed_d or not changed_d <= RISK_KEYS or any(d[k] != base[k] for k in TRAILING_KEYS):
        raise ExperimentError("D may change risk settings only and must retain A's trailing/partial settings")
    e = presets["E_calibrated_risk"]
    changed_e = {k for k in base if e[k] != base[k]}
    if not changed_e or not changed_e <= RISK_KEYS or any(e[k] != base[k] for k in TRAILING_KEYS):
        raise ExperimentError("E may change risk settings only and must retain A's trailing/partial settings")
    if all(e[k] == d[k] for k in RISK_KEYS):
        raise ExperimentError("E must not duplicate D's tight-risk settings")

    numeric_trailing = {
        "InpDynamicStopActivateAtR", "InpDynamicStopBreakevenAtR", "InpDynamicStopATRMult",
        "InpDynamicStopMinImprovementPoints", "InpDynamicStopMaxSpreadPoints", "InpDynamicStopMinATR",
        "InpDynamicStopMaxATR", "InpDynamicStopModifyIntervalSec", "InpDynamicStopStructuralBufferATR",
        "InpBreakEvenAtR", "InpPartialAtR", "InpPartialFraction", "InpTrailATRMult",
    }
    for role, p in presets.items():
        _bool_setting(p, "InpEnableDynamicStop", role)
        _bool_setting(p, "InpDynamicStopUseStructuralAnchor", role)
        for k in numeric_trailing:
            value = _float_setting(p, k, role)
            if k in {"InpDynamicStopActivateAtR", "InpDynamicStopBreakevenAtR", "InpDynamicStopMinImprovementPoints", "InpDynamicStopMaxSpreadPoints", "InpDynamicStopMinATR", "InpDynamicStopMaxATR", "InpDynamicStopModifyIntervalSec", "InpDynamicStopStructuralBufferATR", "InpBreakEvenAtR"} and value < 0:
                raise ExperimentError(f"{role}.{k} cannot be negative")
        if _float_setting(p, "InpDynamicStopATRMult", role) <= 0 or _float_setting(p, "InpTrailATRMult", role) <= 0:
            raise ExperimentError(f"{role} ATR multipliers must be positive")
        if _float_setting(p, "InpPartialAtR", role) <= 0 or not 0 < _float_setting(p, "InpPartialFraction", role) < 1:
            raise ExperimentError(f"{role} partial target/fraction is invalid")
        lo, hi = _float_setting(p, "InpDynamicStopMinATR", role), _float_setting(p, "InpDynamicStopMaxATR", role)
        if lo > 0 and hi > 0 and lo > hi:
            raise ExperimentError(f"{role} minimum ATR exceeds maximum ATR")
        for key in ("InpRiskPercentPerTrade", "InpMaxDailyLossPercent", "InpMaxDrawdownPercent", "InpMaxPortfolioRiskPercent"):
            if _float_setting(p, key, role) <= 0:
                raise ExperimentError(f"{role}.{key} must be positive")
        for key in ("InpMaxOpenTrades", "InpMaxPositionsPerSymbol", "InpMaxPositionsPerGroup"):
            value = _float_setting(p, key, role)
            if value < 1 or not value.is_integer():
                raise ExperimentError(f"{role}.{key} must be a positive integer")
        if not 0 < _float_setting(p, "InpDeriskFloor", role) <= 1:
            raise ExperimentError(f"{role}.InpDeriskFloor must be in (0, 1]")


def _read_open(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or "position_id" not in reader.fieldnames:
                raise ExperimentError(f"open-position CSV must contain position_id header: {path}")
            return list(reader)
    except OSError as exc:
        raise ExperimentError(f"cannot read open positions CSV: {path}") from exc


def _positions(path: Path, ctx: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    required = {"position_id", "time", "entry", "volume", "profit", "commission", "swap", "fee", "risk_cash"}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or required - set(reader.fieldnames):
                raise ExperimentError(f"deal CSV missing required columns: {sorted(required - set(reader.fieldnames or []))}")
            for n, row in enumerate(reader, 2):
                pid = (row.get("position_id") or "").strip()
                if not pid:
                    raise ExperimentError(f"{path}:{n} has no position_id")
                entry = (row.get("entry") or "").strip().lower()
                if entry in {"inout", "entry_inout", "2"}:
                    raise ExperimentError(f"{path}:{n} has inout reversal; split close/open records")
                if entry not in {"in", "out", "out_by", "entry_in", "entry_out", "entry_out_by", "0", "1", "3"}:
                    raise ExperimentError(f"{path}:{n} has unsupported entry field {entry!r}")
                normalized: dict[str, Any] = {"id": pid, "entry": "in" if entry in {"in", "entry_in", "0"} else "out",
                                             "time": _time(row.get("time"), f"{path}:{n}.time")}
                for k in ("volume", "profit", "commission", "swap", "fee", "risk_cash"):
                    try:
                        val = float(row[k]) if row.get(k) not in (None, "") else 0.0
                    except (ValueError, TypeError) as exc:
                        raise ExperimentError(f"{path}:{n} has invalid {k}") from exc
                    if not math.isfinite(val):
                        raise ExperimentError(f"{path}:{n} has non-finite {k}")
                    normalized[k] = val
                if normalized["volume"] <= 0:
                    raise ExperimentError(f"{path}:{n} volume must be positive")
                grouped[pid].append(normalized)
    except OSError as exc:
        raise ExperimentError(f"cannot read deal CSV: {path}") from exc

    result: list[dict[str, Any]] = []
    incomplete = 0
    for pid, deals in grouped.items():
        deals.sort(key=lambda d: d["time"])
        entries = [d for d in deals if d["entry"] == "in"]
        exits = [d for d in deals if d["entry"] == "out"]
        if not entries:
            raise ExperimentError(f"position {pid} has no entry deals")
        open_volume = sum(d["volume"] for d in entries) - sum(d["volume"] for d in exits)
        if open_volume < -1e-7:
            raise ExperimentError(f"position {pid} is over-closed")
        if open_volume > 1e-7 or not exits:
            incomplete += 1
            continue
        entry_time, exit_time = entries[0]["time"], exits[-1]["time"]
        if not (ctx["period_start"] <= entry_time < ctx["period_end"] and ctx["period_start"] <= exit_time < ctx["period_end"]):
            continue
        risks = [d["risk_cash"] for d in entries if d["risk_cash"] > 0]
        if not risks:
            raise ExperimentError(f"closed position {pid} lacks a positive entry risk_cash")
        risk_cash = risks[0]
        if any(abs(v - risk_cash) > max(0.01, risk_cash * 0.02) for v in risks[1:]):
            raise ExperimentError(f"position {pid} contains conflicting initial risk")
        net = sum(d["profit"] + d["commission"] + d["swap"] + d["fee"] for d in deals)
        result.append({"position_id": pid, "entry_time": entry_time, "exit_time": exit_time,
                       "net_pnl": net, "risk_cash": risk_cash, "realized_r": net / risk_cash})
    result.sort(key=lambda p: (p["exit_time"], p["position_id"]))
    return result, incomplete


def _drawdown(pnls: list[float], initial: float) -> tuple[float, float]:
    equity = peak = initial
    max_cash = max_pct = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        dd = max(0.0, peak - equity)
        max_cash = max(max_cash, dd)
        if peak > 0:
            max_pct = max(max_pct, 100 * dd / peak)
    return max_cash, max_pct


def _mc(pnls: list[float], initial: float, simulations: int, seed: int) -> dict[str, Any]:
    if not pnls:
        return {"simulations": 0, "status": "insufficient_data"}
    rng, values = random.Random(seed), list(pnls)
    draws: list[float] = []
    for _ in range(simulations):
        rng.shuffle(values)
        draws.append(_drawdown(values, initial)[1])
    draws.sort()
    def pct(p: float) -> float:
        i = (len(draws) - 1) * p
        lo, hi = math.floor(i), math.ceil(i)
        return draws[lo] if lo == hi else draws[lo] + (draws[hi] - draws[lo]) * (i - lo)
    return {"simulations": simulations, "seed": seed, "method": "permutation_without_replacement",
            "max_drawdown_pct": {f"p{int(p*100)}": pct(p) for p in (0.50, 0.90, 0.95, 0.99)}}


def _metrics(positions: list[dict[str, Any]], ctx: dict[str, Any], simulations: int, seed: int) -> dict[str, Any]:
    pnls = [p["net_pnl"] for p in positions]
    gains, losses, n = sum(v for v in pnls if v > 0), -sum(v for v in pnls if v < 0), len(pnls)
    wins, lost = sum(v > 0 for v in pnls), sum(v < 0 for v in pnls)
    dd_cash, dd_pct = _drawdown(pnls, ctx["initial_balance"])
    return {
        "completed_positions": n, "wins": wins, "losses": lost, "scratches": n - wins - lost,
        "win_rate": wins / n if n else None, "net_pnl": sum(pnls),
        "net_return_pct": 100 * sum(pnls) / ctx["initial_balance"],
        "net_expectancy_cash_per_position": sum(pnls) / n if n else None,
        "net_expectancy_r_per_position": statistics.fmean(p["realized_r"] for p in positions) if n else None,
        "gross_profit_cash": gains, "gross_loss_cash_abs": losses,
        "profit_factor": gains / losses if losses else (None if not gains else "undefined_no_losses"),
        "average_win_cash": statistics.fmean(v for v in pnls if v > 0) if wins else None,
        "average_loss_cash_abs": statistics.fmean(-v for v in pnls if v < 0) if lost else None,
        "max_consecutive_losses": _max_streak(pnls),
        "max_closed_position_drawdown_cash": dd_cash, "max_closed_position_drawdown_pct": dd_pct,
        "monte_carlo_trade_order_drawdown": _mc(pnls, ctx["initial_balance"], simulations, seed),
        "drawdown_caveat": "closed-position only; compare with native MT5 equity/tick-level drawdown",
    }


def _max_streak(pnls: list[float]) -> int:
    best = current = 0
    for v in pnls:
        if v < 0:
            current += 1
            best = max(best, current)
        elif v > 0:
            current = 0
    return best


def compare_manifest(manifest_path: str | Path, *, simulations: int = 2000, seed: int = 20261013) -> tuple[dict[str, Any], dict[str, Any]]:
    if simulations < 1:
        raise ExperimentError("simulations must be positive")
    path = Path(manifest_path).expanduser().resolve()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentError(f"cannot read manifest: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise ExperimentError("manifest schema_version must be 1")
    if not isinstance(doc.get("experiment_id"), str) or not doc["experiment_id"].strip():
        raise ExperimentError("experiment_id must be non-empty")
    ctx = _context(doc.get("test_context"), "test_context")
    dataset = _file(path, doc.get("dataset_path"), "dataset_path")
    if _hash(dataset) != ctx["dataset_sha256"]:
        raise ExperimentError("dataset SHA-256 does not match test_context.dataset_sha256")
    variants = doc.get("variants")
    if not isinstance(variants, list):
        raise ExperimentError("variants must be a list")

    role_data: dict[str, dict[str, Any]] = {}
    presets: dict[str, dict[str, str]] = {}
    artifacts: dict[str, dict[str, Any]] = {}
    run_ids: set[str] = set()
    for i, item in enumerate(variants):
        if not isinstance(item, dict):
            raise ExperimentError(f"variants[{i}] must be an object")
        role = item.get("role")
        if role not in ROLES or role in role_data:
            raise ExperimentError(f"invalid or duplicate role: {role!r}")
        run_id = item.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip() or run_id in run_ids:
            raise ExperimentError(f"{role}.run_id must be unique and non-empty")
        run_ids.add(run_id)
        observed = _context(item.get("observed_context"), f"{role}.observed_context")
        if observed != ctx:
            fields = sorted(k for k in CONTEXT_KEYS if observed[k] != ctx[k])
            raise ExperimentError(f"{role} context differs from the matched test context: {', '.join(fields)}")
        preset_path = _file(path, item.get("input_preset"), f"{role}.input_preset")
        report_path = _file(path, item.get("report_path"), f"{role}.report_path")
        deal_path = _file(path, item.get("deals_csv"), f"{role}.deals_csv")
        open_path = _file(path, item.get("open_positions_csv"), f"{role}.open_positions_csv", allow_empty=True)
        preset = _preset(preset_path)
        presets[role] = preset
        positions, incomplete = _positions(deal_path, ctx)
        open_positions = _read_open(open_path)
        role_data[role] = {"run_id": run_id, "positions": positions, "incomplete": incomplete,
                           "open_count": len(open_positions), "preset": preset}
        artifacts[role] = {
            "input_preset": {"path": str(preset_path), "sha256": _hash(preset_path)},
            "report": {"path": str(report_path), "sha256": _hash(report_path)},
            "deals": {"path": str(deal_path), "sha256": _hash(deal_path)},
            "open_positions": {"path": str(open_path), "sha256": _hash(open_path)},
            "dataset": {"path": str(dataset), "sha256": _hash(dataset)},
        }
    missing = sorted(set(ROLES) - set(role_data))
    if missing:
        raise ExperimentError(f"missing required experiment roles: {', '.join(missing)}")
    _validate_presets(presets)

    start, end = ctx["locked_oos_start"], ctx["locked_oos_end"]
    results: dict[str, Any] = {}
    for role in ROLES:
        record = role_data[role]
        all_positions = record["positions"]
        oos = [p for p in all_positions if start <= p["entry_time"] < end and p["exit_time"] < end]
        results[role] = {
            "run_id": record["run_id"], "input_parameters": record["preset"],
            "artifacts": artifacts[role], "incomplete_positions_excluded": record["incomplete"],
            "open_positions_at_test_end": record["open_count"],
            "full_period": _metrics(all_positions, ctx, simulations, seed),
            "locked_oos": _metrics(oos, ctx, simulations, seed),
        }

    deltas: dict[str, Any] = {}
    numeric = ("net_pnl", "net_return_pct", "net_expectancy_cash_per_position",
               "net_expectancy_r_per_position", "max_closed_position_drawdown_cash",
               "max_closed_position_drawdown_pct", "max_consecutive_losses", "completed_positions")
    baseline = results["A_current_baseline"]
    for role in ROLES[1:]:
        deltas[role] = {}
        for label in ("full_period", "locked_oos"):
            a, b = baseline[label], results[role][label]
            deltas[role][label] = {
                **{k: (b[k] - a[k] if isinstance(a[k], (int, float)) and isinstance(b[k], (int, float)) else None) for k in numeric},
                "profit_factor": {"baseline": a["profit_factor"], "candidate": b["profit_factor"]},
            }

    report = {
        "schema_version": 1, "experiment_id": doc["experiment_id"],
        "generated_at_utc": _iso(datetime.now(timezone.utc)),
        "matched_context_verified": True, "dataset_digest_verified": True,
        "cost_model": {
            "commission_per_lot": ctx["commission_per_lot"], "spread_model": ctx["spread_model"],
            "spread_widening_multiplier": ctx["spread_widening_multiplier"], "slippage_points": ctx["slippage_points"],
            "swap_included": ctx["swap_included"], "costs_applied_in_tester": ctx["costs_applied_in_tester"],
            "net_pnl_source": "sum(deal profit + commission + swap + fee); spread/slippage are represented by actual tester fills under the declared stressed setup",
        },
        "context": {k: (_iso(v) if isinstance(v, datetime) else v) for k, v in ctx.items()},
        "variants": results, "candidate_deltas_vs_A": deltas,
        "promotion_recommendation": None,
        "promotion_note": "No automatic promotion. Require native MT5 equity drawdown, adequate samples, locked-OOS review, walk-forward validation and demo-broker evidence.",
        "limitations": [
            "The comparator analyzes submitted exports; hashes prove identity, not truthful tester configuration.",
            "Monte Carlo permutes observed completed trade P&L without replacement; it measures trade-order sensitivity, not future risk.",
            "Closed-position drawdown omits intratrade equity excursions; native MT5 equity/tick-level reports remain authoritative.",
            "Trailing-off attribution depends on unchanged non-trailing exit behavior; partial-close eligibility is independently tested.",
        ],
    }
    summary = {
        "experiment_id": doc["experiment_id"], "matched_context_verified": True,
        "dataset_digest_verified": True, "variant_roles": list(ROLES),
        "locked_oos_start": _iso(start), "locked_oos_end": _iso(end),
        "promotion_recommendation": None,
    }
    return report, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="five-arm MT5 experiment manifest")
    parser.add_argument("--output", required=True, help="output comparison JSON")
    parser.add_argument("--simulations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261013)
    args = parser.parse_args(argv)
    try:
        report, summary = compare_manifest(args.manifest, simulations=args.simulations, seed=args.seed)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (ExperimentError, OSError) as exc:
        print(f"risk-trailing-experiment: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
