#!/usr/bin/env python3
"""Fail-closed reconciliation of LONA report summaries and reconstructed trade exports.

The LONA trade-history endpoint can expose fewer rows than a stored legacy report.
Stored report metrics are preserved as the platform-authoritative summary; reconstructed
trade P&L is gross of fees and MUST NOT be compared directly to stored net P&L.
An incomplete history is never treated as a smaller complete sample for optimization.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_COST_FLAGS = ("commission", "swap", "spread", "slippage", "broker_fees")


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def reconcile_report(report: dict[str, Any], min_trades: int = 30) -> dict[str, Any]:
    report_id = str(report.get("report_id", "UNKNOWN"))
    metrics = report.get("stored_metrics") or {}
    history = report.get("trade_history") or {}
    costs = report.get("costs") or {}
    blockers: list[str] = []
    warnings: list[str] = []

    stored_count = metrics.get("trade_count")
    if not isinstance(stored_count, int) or stored_count < 0:
        blockers.append("STORED_TRADE_COUNT_MISSING_OR_INVALID")

    rows = history.get("rows")
    has_rows = isinstance(rows, list)
    row_count = len(rows) if has_rows else history.get("reconstructed_count")
    history_total = history.get("reconstructed_total", row_count)
    has_next = history.get("has_next")
    raw_export_complete = history.get("raw_export_complete") is True

    if not isinstance(row_count, int) or row_count < 0:
        blockers.append("RECONSTRUCTED_HISTORY_COUNT_MISSING_OR_INVALID")
    if not isinstance(history_total, int) or history_total < 0:
        blockers.append("RECONSTRUCTED_HISTORY_TOTAL_MISSING_OR_INVALID")
    if has_next is not False:
        blockers.append("RECONSTRUCTED_HISTORY_HAS_NEXT_OR_UNKNOWN")
    if stored_count is not None and isinstance(row_count, int) and stored_count != row_count:
        blockers.append("STORED_AND_RECONSTRUCTED_TRADE_COUNTS_DIFFER")
    if isinstance(row_count, int) and isinstance(history_total, int) and row_count != history_total:
        blockers.append("RECONSTRUCTED_ROW_COUNT_DIFFERS_FROM_ENDPOINT_TOTAL")
    if not raw_export_complete or not has_rows:
        blockers.append("COMPLETE_RAW_TRADE_EXPORT_NOT_AVAILABLE")

    gross_pnl = None
    ledger_wins = ledger_losses = ledger_flats = None
    if has_rows:
        pnl_values = [row.get("pnl") for row in rows]
        if not all(_finite_number(v) for v in pnl_values):
            blockers.append("RECONSTRUCTED_TRADE_PNL_MISSING_OR_INVALID")
        else:
            gross_pnl = round(sum(float(v) for v in pnl_values), 8)
            ledger_wins = sum(float(v) > 0 for v in pnl_values)
            ledger_losses = sum(float(v) < 0 for v in pnl_values)
            ledger_flats = sum(float(v) == 0 for v in pnl_values)

        keys = []
        for row in rows:
            keys.append((row.get("entry_time"), row.get("exit_time"), row.get("direction")))
        if any(not a or not b or not c for a, b, c in keys):
            blockers.append("TRADE_IDENTITY_FIELDS_MISSING")
        elif len(set(keys)) != len(keys):
            blockers.append("DUPLICATE_RECONSTRUCTED_TRADE_IDENTITIES")

    verified_costs = costs.get("verified") is True
    missing_costs = [key for key in REQUIRED_COST_FLAGS if costs.get(key) is not True]
    if not verified_costs or missing_costs:
        blockers.append("TRANSACTION_COSTS_NOT_FULLY_VERIFIED")
    if not costs.get("evidence_reference"):
        blockers.append("BROKER_COST_EVIDENCE_REFERENCE_MISSING")

    win_rate = metrics.get("win_rate_pct")
    profit_factor = metrics.get("profit_factor")
    net_pnl = metrics.get("net_pnl")
    if win_rate == 100 and profit_factor == 0:
        warnings.append("PROFIT_FACTOR_ZERO_WITH_100_PERCENT_WIN_RATE_REQUIRES_EXPLANATION")
        blockers.append("STORED_METRIC_INCONSISTENCY_REQUIRES_EXPLANATION")
    if isinstance(stored_count, int) and stored_count == 0:
        blockers.append("ZERO_TRADES_NO_PERFORMANCE_EVIDENCE")
    elif isinstance(stored_count, int) and stored_count < min_trades:
        blockers.append("BELOW_MINIMUM_TRADE_COUNT_FOR_PERFORMANCE_REVIEW")

    if gross_pnl is not None and _finite_number(net_pnl):
        warnings.append(
            "GROSS_RECONSTRUCTED_PNL_NOT_COMPARED_TO_STORED_NET_PNL; "
            "the history endpoint excludes commissions and fees"
        )

    if "STORED_AND_RECONSTRUCTED_TRADE_COUNTS_DIFFER" in blockers:
        if history.get("legacy_redacted") is True:
            warnings.append("PLATFORM_MARKED_OR_KNOWN_LEGACY_REDACTED_HISTORY")
        else:
            warnings.append("COUNT_MISMATCH_CAUSE_NOT_ESTABLISHED")

    return {
        "report_id": report_id,
        "strategy_id": report.get("strategy_id"),
        "symbol": report.get("symbol"),
        "timeframe": report.get("timeframe"),
        "stored_metrics": {
            "trade_count": stored_count,
            "net_pnl": net_pnl,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "expectancy": metrics.get("expectancy"),
            "max_drawdown_pct": metrics.get("max_drawdown_pct"),
        },
        "reconstructed_history": {
            "row_count": row_count,
            "endpoint_total": history_total,
            "has_next": has_next,
            "raw_export_complete": raw_export_complete,
            "gross_pnl_sum": gross_pnl,
            "observed_wins": ledger_wins,
            "observed_losses": ledger_losses,
            "observed_flats": ledger_flats,
            "win_rate_is_complete_sample": (
                raw_export_complete and isinstance(stored_count, int)
                and isinstance(row_count, int) and row_count == stored_count
                and has_next is False
            ),
        },
        "costs": {
            "verified": verified_costs and not missing_costs,
            "missing_or_unverified_fields": missing_costs,
            "evidence_reference": costs.get("evidence_reference"),
        },
        "blockers": sorted(set(blockers)),
        "warnings": warnings,
        "optimization_allowed": len(blockers) == 0,
        "interpretation": (
            "ELIGIBLE_FOR_HUMAN_REVIEW_NOT_PROOF_OF_PROFITABILITY"
            if not blockers else "BLOCKED_DO_NOT_OPTIMIZE_OR_PROMOTE"
        ),
    }


def audit(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")
    reports = manifest.get("reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("reports must be a non-empty list")
    min_trades = manifest.get("min_trades_for_performance_review", 30)
    if not isinstance(min_trades, int) or min_trades < 1:
        raise ValueError("min_trades_for_performance_review must be a positive integer")
    results = [reconcile_report(item, min_trades=min_trades) for item in reports]
    return {
        "schema_version": 1,
        "audit_type": "lona_report_vs_reconstructed_history",
        "optimization_allowed": all(r["optimization_allowed"] for r in results),
        "report_count": len(results),
        "blocked_report_count": sum(not r["optimization_allowed"] for r in results),
        "results": results,
        "rule": "Never tune or promote from incomplete reconstructed history or unverified transaction costs.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = audit(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "optimization_allowed": result["optimization_allowed"],
        "report_count": result["report_count"],
        "blocked_report_count": result["blocked_report_count"],
        "output": str(args.output),
    }, sort_keys=True))
    return 0 if result["optimization_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
