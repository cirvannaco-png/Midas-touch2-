#!/usr/bin/env python3
"""Cost-complete stress scenarios, walk-forward folds, and trade-order Monte Carlo.

Consumes authentic MT5 deal-history exports. Net P&L starts with each deal's
profit + commission + swap + fee. The observed spread is assumed already
embedded in Strategy Tester fills; this tool adds only incremental spread
widening and per-fill slippage, avoiding a second charge for baseline spread.

This is a research diagnostic, not an MT5 simulator or approval signal.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import math
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from tools.position_ledger_metrics import IN, INOUT, LedgerError, read_deals, read_open_ids, reconstruct_positions
except ImportError:
    from position_ledger_metrics import IN, INOUT, LedgerError, read_deals, read_open_ids, reconstruct_positions


class CostStressError(ValueError):
    """Input data cannot support a cost-complete stress report."""


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def require_explicit_cost_columns(path: Path) -> None:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            header = next(csv.reader(stream), [])
    except OSError as exc:
        raise CostStressError(f"cannot read deal CSV header: {path}") from exc
    normalized = {_norm(item) for item in header}
    aliases = {
        "commission": {"commission", "dealcommission"},
        "swap": {"swap", "dealswap"},
        "fee": {"fee", "dealfee"},
    }
    missing = [field for field, candidates in aliases.items() if not (normalized & candidates)]
    if missing:
        raise CostStressError(
            "cost-complete analysis requires explicit deal CSV columns (zero values are valid): "
            + ", ".join(missing)
        )


def parse_csv_numbers(value: str, name: str) -> list[float]:
    try:
        values = [float(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise CostStressError(f"{name} must be a comma-separated list of numbers") from exc
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise CostStressError(f"{name} must contain finite non-negative values")
    return sorted(set(values))


def _dt(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise CostStressError(f"{name} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CostStressError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - index) + ordered[high] * (index - low)


def performance_metrics(pnls: list[float], initial_balance: float) -> dict:
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    equity = initial_balance
    peak = initial_balance
    max_dd = max_dd_pct = 0.0
    longest = current = 0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        if peak > 0:
            max_dd_pct = max(max_dd_pct, 100.0 * dd / peak)
        if pnl < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return {
        "trades": len(pnls),
        "net_pnl": round(sum(pnls), 8),
        "ending_balance": round(equity, 8),
        "profit_factor": round(gross_profit / gross_loss, 8) if gross_loss > 0 else ("no_losses" if gross_profit > 0 else None),
        "win_rate_pct": round(100.0 * len(wins) / len(pnls), 6) if pnls else None,
        "expectancy_per_trade": round(sum(pnls) / len(pnls), 8) if pnls else None,
        "average_win": round(sum(wins) / len(wins), 8) if wins else None,
        "average_loss_abs": round(gross_loss / len(losses), 8) if losses else None,
        "max_consecutive_losses": longest,
        "max_closed_trade_drawdown_cash": round(max_dd, 8),
        "max_closed_trade_drawdown_pct": round(max_dd_pct, 8),
    }


def incremental_cost_for_position(turnover_volume: float, point_value_per_lot: float,
                                  spread_widening_points: float,
                                  slippage_points_per_fill: float) -> float:
    """Cost using all opening/closing deal volumes, without double-charging baseline spread.

    Spread widening is a change in full spread, so each executed side pays half
    of that expansion. Slippage applies independently to each deal-side fill.
    """
    if turnover_volume < 0 or point_value_per_lot <= 0:
        raise CostStressError("turnover volume must be >= 0 and point value must be > 0")
    if min(spread_widening_points, slippage_points_per_fill) < 0:
        raise CostStressError("incremental cost assumptions cannot be negative")
    points_per_side = spread_widening_points / 2.0 + slippage_points_per_fill
    return turnover_volume * point_value_per_lot * points_per_side


def _walk_forward_folds(positions: list[dict], start: datetime, end: datetime,
                        train_months: int, test_months: int, folds: int,
                        spread_points: float, slippage_points: float,
                        point_value: float, initial_balance: float) -> list[dict]:
    def shift_months(value: datetime, months: int) -> datetime:
        month_index = value.year * 12 + value.month - 1 + months
        year, month0 = divmod(month_index, 12)
        month = month0 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)

    def adjusted(rows):
        return [p["net_pnl"] - incremental_cost_for_position(
            p["turnover_volume"], point_value, spread_points, slippage_points
        ) for p in rows]

    output = []
    test_start = shift_months(start, train_months)
    for index in range(folds):
        test_end = min(shift_months(test_start, test_months), end)
        if test_start >= end or test_end <= test_start:
            break
        train_start = shift_months(test_start, -train_months)
        train = [p for p in positions if train_start <= p["opened_at"] < test_start and p["closed_at"] < test_start]
        test = [p for p in positions if test_start <= p["opened_at"] < test_end and p["closed_at"] < test_end]
        output.append({
            "fold": index + 1,
            "train_start": train_start.isoformat(),
            "train_end": test_start.isoformat(),
            "test_start": test_start.isoformat(),
            "test_end": test_end.isoformat(),
            "train": performance_metrics(adjusted(train), initial_balance),
            "test": performance_metrics(adjusted(test), initial_balance),
            "test_boundary_censored": sum(
                1 for p in positions if test_start <= p["opened_at"] < test_end and p["closed_at"] >= test_end
            ),
        })
        test_start = test_end
    return output


def monte_carlo_drawdown(pnls: list[float], initial_balance: float, simulations: int, seed: int) -> dict:
    if simulations < 100:
        raise CostStressError("simulations must be at least 100")
    if not pnls:
        return {"simulations": simulations, "trade_shuffle_without_replacement": None, "bootstrap_with_replacement": None}
    rng = random.Random(seed)
    shuffled_dd, shuffled_dd_pct, shuffled_streak = [], [], []
    bootstrap_dd, bootstrap_dd_pct, bootstrap_end, bootstrap_streak = [], [], [], []
    n = len(pnls)
    for _ in range(simulations):
        order = list(pnls)
        rng.shuffle(order)
        stats = performance_metrics(order, initial_balance)
        shuffled_dd.append(stats["max_closed_trade_drawdown_cash"])
        shuffled_dd_pct.append(stats["max_closed_trade_drawdown_pct"])
        shuffled_streak.append(float(stats["max_consecutive_losses"]))
        sample = [pnls[rng.randrange(n)] for _ in range(n)]
        sampled = performance_metrics(sample, initial_balance)
        bootstrap_dd.append(sampled["max_closed_trade_drawdown_cash"])
        bootstrap_dd_pct.append(sampled["max_closed_trade_drawdown_pct"])
        bootstrap_end.append(sampled["ending_balance"])
        bootstrap_streak.append(float(sampled["max_consecutive_losses"]))

    def summary(dd, dd_pct, streak, ending=None):
        out = {
            "max_drawdown_cash_p05_p50_p95": [round(_percentile(dd, p), 8) for p in (0.05, 0.50, 0.95)],
            "max_drawdown_pct_p05_p50_p95": [round(_percentile(dd_pct, p), 8) for p in (0.05, 0.50, 0.95)],
            "max_consecutive_losses_p05_p50_p95": [round(_percentile(streak, p), 4) for p in (0.05, 0.50, 0.95)],
        }
        if ending is not None:
            out["ending_balance_p05_p50_p95"] = [round(_percentile(ending, p), 8) for p in (0.05, 0.50, 0.95)]
        return out

    return {
        "simulations": simulations,
        "seed": seed,
        "trade_shuffle_without_replacement": summary(shuffled_dd, shuffled_dd_pct, shuffled_streak),
        "bootstrap_with_replacement": summary(bootstrap_dd, bootstrap_dd_pct, bootstrap_streak, bootstrap_end),
        "interpretation": "Shuffles preserve the observed net P&L sample and total result; bootstrap samples with replacement illustrate sampling uncertainty. Neither predicts future returns or replaces tick-level MT5 equity drawdown."
    }


def build_report(deals_path: Path, open_ids_path: Path, *, point_value_per_lot: float,
                 initial_balance: float, spread_stresses: list[float], slippage_stresses: list[float],
                 start: datetime, end: datetime, train_months: int, test_months: int, folds: int,
                 simulations: int, seed: int) -> dict:
    require_explicit_cost_columns(deals_path)
    try:
        deals = read_deals(deals_path)
        open_ids = read_open_ids(open_ids_path)
        positions, ignored = reconstruct_positions(deals, open_ids)
    except (OSError, LedgerError) as exc:
        raise CostStressError(str(exc)) from exc
    positions = [p for p in positions if start <= p["opened_at"] < end and p["closed_at"] < end]
    by_id: dict[str, list[dict]] = {}
    for deal in deals:
        by_id.setdefault(str(deal["position_id"]), []).append(deal)
    for position in positions:
        position["turnover_volume"] = sum(float(d["volume"]) for d in by_id[position["position_id"]])
    if not positions:
        raise CostStressError("no fully closed positions remain inside the declared evaluation window")
    report = {
        "schema_version": 1,
        "scope": {
            "deals_csv": str(deals_path),
            "open_positions_csv": str(open_ids_path),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "point_value_per_lot": point_value_per_lot,
            "initial_balance": initial_balance,
            "commission_swap_and_fee": "from explicit deal-history columns; do not add commission a second time",
            "baseline_spread": "assumed embedded in MT5 fill profit; stress cases add only spread widening beyond baseline",
            "slippage": "incremental per executed deal-side fill; specified in points",
            "ignored_ledger_groups": ignored,
            "completed_positions_in_window": len(positions),
        },
        "scenarios": [],
    }
    for spread in spread_stresses:
        for slippage in slippage_stresses:
            pnls = [
                p["net_pnl"] - incremental_cost_for_position(
                    p["turnover_volume"], point_value_per_lot, spread, slippage
                ) for p in positions
            ]
            total_cost = sum(p["net_pnl"] - pnl for p, pnl in zip(positions, pnls))
            report["scenarios"].append({
                "incremental_spread_widening_points": spread,
                "incremental_slippage_points_per_fill": slippage,
                "incremental_stress_cost": round(total_cost, 8),
                "metrics": performance_metrics(pnls, initial_balance),
                "walk_forward": _walk_forward_folds(
                    positions, start, end, train_months, test_months, folds, spread, slippage,
                    point_value_per_lot, initial_balance
                ),
                "monte_carlo": monte_carlo_drawdown(pnls, initial_balance, simulations, seed),
            })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deals", required=True, type=Path, help="MT5 deals CSV with explicit commission/swap/fee columns")
    parser.add_argument("--open-positions", required=True, type=Path, help="MT5 open-position IDs CSV with a header")
    parser.add_argument("--point-value-per-lot", required=True, type=float, help="account-currency value of one symbol point for 1.0 lot from the exact tested symbol specification")
    parser.add_argument("--initial-balance", type=float, default=10000.0)
    parser.add_argument("--start", required=True, help="inclusive, timezone-aware ISO-8601 start")
    parser.add_argument("--end", required=True, help="exclusive, timezone-aware ISO-8601 end")
    parser.add_argument("--spread-widening-points", default="0,2,5")
    parser.add_argument("--slippage-points-per-fill", default="0,1,2")
    parser.add_argument("--train-months", type=int, default=6)
    parser.add_argument("--test-months", type=int, default=2)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--simulations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20261013)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        start, end = _dt(args.start, "start"), _dt(args.end, "end")
        if not start < end:
            raise CostStressError("start must precede end")
        if not math.isfinite(args.point_value_per_lot) or args.point_value_per_lot <= 0:
            raise CostStressError("point-value-per-lot must be finite and > 0")
        if not math.isfinite(args.initial_balance) or args.initial_balance <= 0:
            raise CostStressError("initial balance must be finite and > 0")
        if args.train_months <= 0 or args.test_months <= 0 or args.folds <= 0:
            raise CostStressError("train-months, test-months, and folds must be > 0")
        spreads = parse_csv_numbers(args.spread_widening_points, "spread-widening-points")
        slippages = parse_csv_numbers(args.slippage_points_per_fill, "slippage-points-per-fill")
        report = build_report(
            args.deals, args.open_positions, point_value_per_lot=args.point_value_per_lot,
            initial_balance=args.initial_balance, spread_stresses=spreads, slippage_stresses=slippages,
            start=start, end=end, train_months=args.train_months, test_months=args.test_months,
            folds=args.folds, simulations=args.simulations, seed=args.seed,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "positions": report["scope"]["completed_positions_in_window"], "scenarios": len(report["scenarios"]), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}, indent=2))
        return 0
    except (CostStressError, LedgerError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
