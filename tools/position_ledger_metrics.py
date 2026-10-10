#!/usr/bin/env python3
"""Position-level MT5 deal-ledger metrics; partial closes count as one position.

CSV requires position_id, time, entry (DEAL_ENTRY), volume, and profit.
Optional monetary columns: commission, swap, fee, risk_cash, lane.
Drawdown is settlement-by-completed-position, not MT5 tick-level equity drawdown.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ALIASES = {
    "position_id": ("position_id", "position", "position_identifier", "identifier", "deal_position_id", "positionid"),
    "time": ("time", "deal_time", "close_time", "timestamp", "date", "dealtime"),
    "entry": ("entry", "deal_entry", "entry_type", "dealentry"),
    "volume": ("volume", "lots", "deal_volume", "size"),
    "profit": ("profit", "deal_profit", "pnl", "realized_pnl"),
    "commission": ("commission", "deal_commission"),
    "swap": ("swap", "deal_swap"),
    "fee": ("fee", "deal_fee"),
    "risk_cash": ("risk_cash", "initial_risk_cash", "planned_risk", "risk_amount"),
    "lane": ("lane", "risk_lane", "entry_lane"),
}
IN = {"in", "deal_entry_in", "entry_in", "0"}
OUT = {"out", "deal_entry_out", "entry_out", "1"}
OUT_BY = {"out_by", "outby", "deal_entry_out_by", "entry_out_by", "3"}
INOUT = {"inout", "in_out", "deal_entry_inout", "entry_inout", "2"}
EPS = 1e-7


class LedgerError(ValueError):
    pass


def norm(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def number(value, field, row_num, default=None):
    if value is None or str(value).strip() == "":
        if default is not None:
            return default
        raise LedgerError(f"row {row_num}: missing {field}")
    raw = str(value).strip().replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(",", "")
    try:
        result = float(raw)
    except ValueError as exc:
        raise LedgerError(f"row {row_num}: invalid {field} value {value!r}") from exc
    if not math.isfinite(result):
        raise LedgerError(f"row {row_num}: non-finite {field}")
    return result


def parse_time(value, row_num):
    raw = (value or "").strip()
    for fmt in (None, "%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S"):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00")) if fmt is None else datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    raise LedgerError(f"row {row_num}: unsupported timestamp {raw!r}")


def resolve_columns(fieldnames, required):
    if not fieldnames:
        raise LedgerError("CSV is missing a header")
    by_norm = {norm(name): name for name in fieldnames}
    result = {}
    for canonical, options in ALIASES.items():
        for option in options:
            if norm(option) in by_norm:
                result[canonical] = by_norm[norm(option)]
                break
    missing = [key for key in required if key not in result]
    if missing:
        raise LedgerError("missing required CSV columns: " + ", ".join(missing))
    return result


def read_deals(path):
    deals = []
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        cols = resolve_columns(reader.fieldnames, ("position_id", "time", "entry", "volume", "profit"))
        for row_num, row in enumerate(reader, 2):
            pid = str(row.get(cols["position_id"], "")).strip()
            entry = re.sub(r"[\s-]+", "_", str(row.get(cols["entry"], "")).strip().lower())
            if not pid:
                raise LedgerError(f"row {row_num}: blank position identifier")
            if entry not in IN | OUT | OUT_BY | INOUT:
                raise LedgerError(f"row {row_num}: unknown entry type {row.get(cols['entry'])!r}")
            volume = number(row.get(cols["volume"]), "volume", row_num)
            if volume < 0:
                raise LedgerError(f"row {row_num}: negative volume")
            item = {
                "position_id": pid, "time": parse_time(row.get(cols["time"], ""), row_num),
                "entry": entry, "volume": volume,
                "profit": number(row.get(cols["profit"]), "profit", row_num),
                "commission": number(row.get(cols["commission"]) if "commission" in cols else None, "commission", row_num, 0.0),
                "swap": number(row.get(cols["swap"]) if "swap" in cols else None, "swap", row_num, 0.0),
                "fee": number(row.get(cols["fee"]) if "fee" in cols else None, "fee", row_num, 0.0),
                "risk_cash": number(row.get(cols["risk_cash"]) if "risk_cash" in cols else None, "risk_cash", row_num, 0.0),
                "lane": str(row.get(cols["lane"], "")).strip().upper() if "lane" in cols else "",
                "source_row": row_num,
            }
            deals.append(item)
    if not deals:
        raise LedgerError("CSV contains no deal rows")
    return deals


def read_open_ids(path):
    if not path:
        return set()
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        cols = resolve_columns(reader.fieldnames, ("position_id",))
        return {str(row.get(cols["position_id"], "")).strip() for row in reader if str(row.get(cols["position_id"], "")).strip()}


def reconstruct_positions(deals, open_ids=None):
    grouped = defaultdict(list)
    for deal in deals:
        grouped[deal["position_id"]].append(deal)
    ignored = {"open_position": 0, "incomplete_volume": 0, "inout_ambiguous": 0}
    positions = []
    for pid, rows in grouped.items():
        rows.sort(key=lambda r: (r["time"], r["source_row"]))
        if pid in (open_ids or set()):
            ignored["open_position"] += 1
            continue
        if any(r["entry"] in INOUT for r in rows):
            ignored["inout_ambiguous"] += 1
            continue
        entries = [r for r in rows if r["entry"] in IN]
        exits = [r for r in rows if r["entry"] in OUT | OUT_BY]
        opened = sum(r["volume"] for r in entries)
        closed = sum(r["volume"] for r in exits)
        tolerance = max(EPS, opened * 1e-5)
        if not entries or not exits or opened <= 0 or closed + tolerance < opened:
            ignored["incomplete_volume"] += 1
            continue
        if closed > opened + tolerance:
            ignored["inout_ambiguous"] += 1
            continue
        risks = [r["risk_cash"] for r in rows if r["risk_cash"] > 0]
        if risks and max(risks) - min(risks) > max(0.01, max(risks) * 0.01):
            raise LedgerError(f"position {pid}: risk_cash differs by more than 1% between rows")
        lanes = {r["lane"] for r in rows if r["lane"]}
        if len(lanes) > 1:
            raise LedgerError(f"position {pid}: conflicting lane labels {sorted(lanes)}")
        net = sum(r["profit"] + r["commission"] + r["swap"] + r["fee"] for r in rows)
        positions.append({
            "position_id": pid, "opened_at": min(r["time"] for r in entries),
            "closed_at": max(r["time"] for r in exits), "opening_volume": opened,
            "closing_volume": closed, "rows": len(rows), "exit_rows": len(exits),
            "gross_profit": sum(r["profit"] for r in rows),
            "commission": sum(r["commission"] for r in rows),
            "swap": sum(r["swap"] for r in rows), "fee": sum(r["fee"] for r in rows),
            "net_pnl": net, "risk_cash": risks[0] if risks else None,
            "lane": next(iter(lanes), "UNTAGGED"),
        })
    positions.sort(key=lambda p: (p["closed_at"], p["position_id"]))
    return positions, ignored


def calculate_metrics(positions, initial_balance=10000.0, ignored=None):
    if not math.isfinite(initial_balance) or initial_balance <= 0:
        raise LedgerError("initial balance must be finite and positive")
    wins = [p for p in positions if p["net_pnl"] > EPS]
    losses = [p for p in positions if p["net_pnl"] < -EPS]
    flats = [p for p in positions if abs(p["net_pnl"]) <= EPS]
    gross_win = sum(p["net_pnl"] for p in wins)
    gross_loss = abs(sum(p["net_pnl"] for p in losses))
    pnl = sum(p["net_pnl"] for p in positions)
    balance, peak, max_dd, max_dd_pct = initial_balance, initial_balance, 0.0, 0.0
    equity = [{"time": None, "balance": initial_balance, "position_id": None}]
    for p in positions:
        balance += p["net_pnl"]
        peak = max(peak, balance)
        dd = peak - balance
        dd_pct = 100 * dd / peak if peak > 0 else (100.0 if dd > 0 else 0.0)
        max_dd, max_dd_pct = max(max_dd, dd), max(max_dd_pct, dd_pct)
        equity.append({"time": p["closed_at"].isoformat(), "balance": round(balance, 8), "position_id": p["position_id"]})
    lanes = {}
    for lane in sorted({p["lane"] for p in positions}):
        rows = [p for p in positions if p["lane"] == lane]
        lane_w = [p for p in rows if p["net_pnl"] > EPS]
        lane_l = [p for p in rows if p["net_pnl"] < -EPS]
        lp = sum(p["net_pnl"] for p in lane_w)
        ll = abs(sum(p["net_pnl"] for p in lane_l))
        lanes[lane] = {
            "positions": len(rows), "net_pnl": round(sum(p["net_pnl"] for p in rows), 2),
            "win_rate_pct_excluding_flats": round(100 * len(lane_w) / (len(lane_w) + len(lane_l)), 2) if lane_w or lane_l else None,
            "profit_factor": round(lp / ll, 4) if ll else (None if not lp else "no_losses"),
        }
    r_values = [p["net_pnl"] / p["risk_cash"] for p in positions if p["risk_cash"] and p["risk_cash"] > 0]
    return {
        "status": "completed" if positions else "no_complete_positions",
        "initial_balance": round(initial_balance, 2), "final_balance": round(balance, 2),
        "net_pnl": round(pnl, 2), "account_return_pct": round(100 * pnl / initial_balance, 4),
        "completed_positions": len(positions), "partial_exit_rows_collapsed": sum(max(0, p["exit_rows"] - 1) for p in positions),
        "wins": len(wins), "losses": len(losses), "breakeven_positions": len(flats),
        "position_win_rate_pct_including_flats": round(100 * len(wins) / len(positions), 2) if positions else None,
        "win_rate_pct_excluding_flats": round(100 * len(wins) / (len(wins) + len(losses)), 2) if wins or losses else None,
        "gross_profit": round(gross_win, 2), "gross_loss_abs": round(gross_loss, 2),
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss else (None if not gross_win else "no_losses"),
        "average_win": round(sum(p["net_pnl"] for p in wins) / len(wins), 2) if wins else None,
        "average_loss": round(sum(p["net_pnl"] for p in losses) / len(losses), 2) if losses else None,
        "average_position_pnl": round(pnl / len(positions), 2) if positions else None,
        "max_closed_position_drawdown_cash": round(max_dd, 2), "max_closed_position_drawdown_pct": round(max_dd_pct, 4),
        "average_realized_R": round(sum(r_values) / len(r_values), 4) if r_values else None,
        "positions_with_risk_cash": len(r_values), "by_lane": lanes, "ignored_groups": ignored or {},
        "drawdown_basis": "closed-position settlement sequence, not tick-level equity",
        "target_account_return_pct": 87.0, "target_profit_from_10000": 8700.0,
        "target_reached": pnl >= 8700.0 if abs(initial_balance - 10000.0) < 0.01 else None,
        "equity_curve": equity,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deals_csv")
    parser.add_argument("--open-positions", help="optional CSV of current position IDs to exclude")
    parser.add_argument("--initial-balance", type=float, default=10000.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        positions, ignored = reconstruct_positions(read_deals(args.deals_csv), read_open_ids(args.open_positions))
        report = calculate_metrics(positions, args.initial_balance, ignored)
    except (OSError, LedgerError) as exc:
        print(f"position_ledger_metrics: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, allow_nan=False))
    else:
        print("POSITION-LEVEL PERFORMANCE")
        print(f"Balance: {report['initial_balance']:.2f} -> {report['final_balance']:.2f}")
        print(f"Net P&L: {report['net_pnl']:+.2f} ({report['account_return_pct']:+.2f}%)")
        print(f"Closed positions: {report['completed_positions']} | partial exit rows collapsed: {report['partial_exit_rows_collapsed']}")
        print(f"Win rate (exclude flats): {report['win_rate_pct_excluding_flats']}% | Profit factor: {report['profit_factor']}")
        print(f"Average win/loss: {report['average_win']} / {report['average_loss']}")
        print(f"Closed-position drawdown: {report['max_closed_position_drawdown_cash']:.2f} ({report['max_closed_position_drawdown_pct']:.2f}%)")
        print(f"87% account-return target reached: {report['target_reached']}")
        print("Warning: drawdown is closed-position based, not tick-level equity drawdown.")
    return 0 if positions else 1


if __name__ == "__main__":
    raise SystemExit(main())
