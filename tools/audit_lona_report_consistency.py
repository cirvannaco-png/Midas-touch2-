#!/usr/bin/env python3
"""Reconcile LONA tranche-level report metrics with grouped position history.

The current Midas-Touch2 LONA strategy opens three parent tranches per setup
(50/20/30 fractions by default). LONA's stored analyzer metrics count each
closed tranche, while the reconstructed history endpoint returns the aggregate
round-trip for each position group. The audit verifies that relationship and
reconciles group gross P&L less the report's simulated commission to stored net
P&L. Per-tranche win/loss attribution is not recoverable from grouped rows.
Broker costs remain a separate promotion requirement.
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


def _group_metrics(rows: list[dict[str, Any]], commission_rate: float, initial_cash: float) -> dict[str, Any]:
    prepared: list[tuple[dict[str, Any], float, float]] = []
    for row in rows:
        gross = row.get("pnl")
        quantity = row.get("quantity")
        entry = row.get("entry_price")
        exit_price = row.get("exit_price")
        if not all(_finite_number(v) for v in (gross, quantity, entry, exit_price)):
            raise ValueError("group history lacks finite P&L, quantity, entry, or exit price")
        if float(quantity) < 0:
            raise ValueError("group quantity must be non-negative")
        # The LONA report's commission schema applies the rate to entry plus
        # exit notional. This reconciles the simulator's net P&L; it is not a
        # claim that this rate is the live broker's commission schedule.
        commission = commission_rate * float(quantity) * (abs(float(entry)) + abs(float(exit_price)))
        net = float(gross) - commission
        prepared.append((row, commission, net))

    prepared.sort(key=lambda v: (str(v[0].get("exit_time", "")), str(v[0].get("entry_time", ""))))
    net_values = [item[2] for item in prepared]
    wins = sum(v > 0 for v in net_values)
    losses = sum(v < 0 for v in net_values)
    flats = sum(v == 0 for v in net_values)
    positive = sum(v for v in net_values if v > 0)
    negative = sum(-v for v in net_values if v < 0)

    equity = initial_cash
    peak = initial_cash
    max_dd_cash = 0.0
    for pnl in net_values:
        equity += pnl
        peak = max(peak, equity)
        max_dd_cash = max(max_dd_cash, peak - equity)

    gross_pnl = sum(float(row["pnl"]) for row in rows)
    simulated_commission = sum(item[1] for item in prepared)
    net_pnl = sum(net_values)
    return {
        "group_count": len(rows),
        "gross_pnl": round(gross_pnl, 8),
        "simulated_commission_from_report_schema": round(simulated_commission, 8),
        "net_pnl_after_report_simulated_commission": round(net_pnl, 8),
        "wins": wins,
        "losses": losses,
        "flats": flats,
        "win_rate_pct": round(100.0 * wins / len(rows), 6) if rows else None,
        "profit_factor": round(positive / negative, 8) if negative > 0 else None,
        "expectancy_per_position_group": round(net_pnl / len(rows), 8) if rows else None,
        "max_close_equity_drawdown_cash": round(max_dd_cash, 8),
        "max_close_equity_drawdown_pct": round(100.0 * max_dd_cash / peak, 8) if peak > 0 else None,
        "closed_group_net_pnl": [round(v, 8) for v in net_values],
        "drawdown_method": "chronological group exits; not native intratrade/equity drawdown",
    }


def reconcile_report(report: dict[str, Any], min_groups: int = 30, pnl_tolerance: float = 0.02) -> dict[str, Any]:
    report_id = str(report.get("report_id", "UNKNOWN"))
    metrics = report.get("stored_metrics") or {}
    history = report.get("trade_history") or {}
    grouping = history.get("grouping") or {}
    simulation = report.get("simulation") or {}
    costs = report.get("costs") or {}
    reconciliation_blockers: list[str] = []
    promotion_blockers: list[str] = []
    warnings: list[str] = []

    stored_count = metrics.get("trade_count")
    if not isinstance(stored_count, int) or stored_count < 0:
        reconciliation_blockers.append("STORED_TRADE_COUNT_MISSING_OR_INVALID")

    rows = history.get("rows")
    has_rows = isinstance(rows, list)
    row_count = len(rows) if has_rows else history.get("reconstructed_count")
    history_total = history.get("reconstructed_total", row_count)
    has_next = history.get("has_next")
    raw_export_complete = history.get("raw_export_complete") is True
    tranches_per_group = grouping.get("tranches_per_group")
    stored_unit = metrics.get("trade_count_unit")
    history_unit = grouping.get("history_unit")
    unit_evidence = grouping.get("unit_semantics_evidence")

    if not isinstance(row_count, int) or row_count < 0:
        reconciliation_blockers.append("RECONSTRUCTED_GROUP_COUNT_MISSING_OR_INVALID")
    if not isinstance(history_total, int) or history_total < 0:
        reconciliation_blockers.append("RECONSTRUCTED_GROUP_TOTAL_MISSING_OR_INVALID")
    if has_next is not False:
        reconciliation_blockers.append("RECONSTRUCTED_HISTORY_HAS_NEXT_OR_UNKNOWN")
    if isinstance(row_count, int) and isinstance(history_total, int) and row_count != history_total:
        reconciliation_blockers.append("RECONSTRUCTED_GROUP_COUNT_DIFFERS_FROM_ENDPOINT_TOTAL")
    if not raw_export_complete or not has_rows:
        reconciliation_blockers.append("COMPLETE_GROUP_HISTORY_EXPORT_NOT_AVAILABLE")

    unit_relationship_verified = False
    if (
        isinstance(stored_count, int)
        and isinstance(row_count, int)
        and isinstance(tranches_per_group, int)
        and tranches_per_group >= 1
        and stored_unit == "closed_tranche"
        and history_unit == "position_group"
        and isinstance(unit_evidence, str)
        and unit_evidence.strip()
        and stored_count == row_count * tranches_per_group
    ):
        unit_relationship_verified = True
        warnings.append(
            f"UNIT_OF_ANALYSIS_RECONCILED: stored {stored_count} closed tranches represent "
            f"{row_count} position groups at {tranches_per_group} tranches per group"
        )
    elif stored_count == 0 and row_count == 0:
        unit_relationship_verified = True
    else:
        reconciliation_blockers.append("TRADE_UNIT_SEMANTICS_NOT_RECONCILED")

    if has_rows:
        identities = [
            (row.get("entry_time"), row.get("exit_time"), row.get("direction"))
            for row in rows
        ]
        if any(not all(identity) for identity in identities):
            reconciliation_blockers.append("GROUP_IDENTITY_FIELDS_MISSING")
        elif len(set(identities)) != len(identities):
            reconciliation_blockers.append("DUPLICATE_GROUP_IDENTITIES")

    commission_rate = simulation.get("commission_rate")
    initial_cash = simulation.get("initial_cash", 10000.0)
    group_stats = None
    if has_rows and isinstance(rows, list) and rows:
        if not _finite_number(commission_rate) or float(commission_rate) < 0:
            reconciliation_blockers.append("REPORT_COMMISSION_SCHEMA_MISSING_OR_INVALID")
        elif not _finite_number(initial_cash) or float(initial_cash) <= 0:
            reconciliation_blockers.append("INITIAL_CASH_MISSING_OR_INVALID")
        else:
            try:
                group_stats = _group_metrics(rows, float(commission_rate), float(initial_cash))
            except (ValueError, KeyError) as exc:
                reconciliation_blockers.append("GROUP_PNL_RECONSTRUCTION_FAILED")
                warnings.append(str(exc))

    net_pnl = metrics.get("net_pnl")
    net_pnl_reconciled = False
    if row_count == 0 and stored_count == 0 and _finite_number(net_pnl) and abs(float(net_pnl)) <= pnl_tolerance:
        net_pnl_reconciled = True
    elif group_stats is not None and _finite_number(net_pnl):
        net_pnl_reconciled = abs(group_stats["net_pnl_after_report_simulated_commission"] - float(net_pnl)) <= pnl_tolerance
        if not net_pnl_reconciled:
            reconciliation_blockers.append("STORED_NET_PNL_NOT_RECONCILED_TO_GROUP_HISTORY")
        else:
            warnings.append(
                "GROUP_NET_PNL_RECONCILED: grouped gross P&L less the report's simulated commission "
                "matches stored net P&L within tolerance; broker costs are not thereby verified"
            )
    else:
        reconciliation_blockers.append("STORED_NET_PNL_OR_GROUP_HISTORY_UNAVAILABLE")

    costs_verified = costs.get("verified") is True
    missing_costs = [key for key in REQUIRED_COST_FLAGS if costs.get(key) is not True]
    if not costs_verified or missing_costs:
        promotion_blockers.append("TRANSACTION_COSTS_NOT_BROKER_VERIFIED")
    if not costs.get("evidence_reference"):
        promotion_blockers.append("BROKER_COST_EVIDENCE_REFERENCE_MISSING")

    group_count = row_count if isinstance(row_count, int) else 0
    if group_count == 0:
        promotion_blockers.append("ZERO_POSITION_GROUPS_NO_PERFORMANCE_EVIDENCE")
    elif group_count < min_groups:
        promotion_blockers.append("BELOW_MINIMUM_POSITION_GROUP_COUNT_FOR_PERFORMANCE_REVIEW")

    if group_stats is not None and group_stats["losses"] == 0 and metrics.get("profit_factor") == 0:
        warnings.append(
            "STORED_PROFIT_FACTOR_ZERO_WITH_NO_GROUP_LOSSES: the platform appears to use zero as a "
            "no-loss-denominator sentinel; use null/undefined for conventional grouped PF instead"
        )
    if (
        _finite_number(metrics.get("win_rate_pct"))
        and group_stats is not None
        and _finite_number(group_stats.get("win_rate_pct"))
        and metrics.get("trade_count") != group_stats.get("group_count")
    ):
        warnings.append(
            "WIN_RATE_UNIT_DIFFERENCE: stored win rate is tranche-level; grouped-history win rate is "
            "position-group-level and should be used for setup-level evaluation"
        )

    reconciliation_blockers = sorted(set(reconciliation_blockers))
    promotion_blockers = sorted(set(promotion_blockers))
    history_reconciled = not reconciliation_blockers and unit_relationship_verified and net_pnl_reconciled
    return {
        "report_id": report_id,
        "strategy_id": report.get("strategy_id"),
        "symbol": report.get("symbol"),
        "timeframe": report.get("timeframe"),
        "stored_metrics": {
            "trade_count": stored_count,
            "trade_count_unit": stored_unit,
            "net_pnl": net_pnl,
            "tranche_win_rate_pct": metrics.get("win_rate_pct"),
            "tranche_profit_factor": metrics.get("profit_factor"),
            "tranche_expectancy": metrics.get("expectancy"),
            "stored_max_drawdown_pct": metrics.get("max_drawdown_pct"),
        },
        "reconstructed_history": {
            "position_group_count": row_count,
            "endpoint_total": history_total,
            "has_next": has_next,
            "raw_export_complete": raw_export_complete,
            "history_unit": history_unit,
            "tranches_per_group": tranches_per_group,
            "unit_relationship_verified": unit_relationship_verified,
            "aggregate_net_pnl_reconciled": net_pnl_reconciled,
            "group_level_metrics": group_stats,
        },
        "costs": {
            "broker_verified": costs_verified and not missing_costs,
            "missing_or_unverified_fields": missing_costs,
            "evidence_reference": costs.get("evidence_reference"),
            "report_commission_rate": commission_rate,
            "report_commission_is_broker_verified": False,
        },
        "reconciliation_blockers": reconciliation_blockers,
        "promotion_blockers": promotion_blockers,
        "warnings": warnings,
        "history_reconciled": history_reconciled,
        "optimization_allowed": history_reconciled and not promotion_blockers,
        "interpretation": (
            "RECONCILED_POSITION_GROUP_HISTORY_NOT_PROMOTION_CERTIFIED"
            if history_reconciled and promotion_blockers
            else "RECONCILED_AND_ELIGIBLE_FOR_HUMAN_REVIEW_NOT_PROOF_OF_PROFITABILITY"
            if history_reconciled
            else "BLOCKED_UNRESOLVED_HISTORY_RECONCILIATION"
        ),
    }


def audit(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")
    reports = manifest.get("reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("reports must be a non-empty list")
    min_groups = manifest.get("min_groups_for_performance_review", 30)
    if not isinstance(min_groups, int) or min_groups < 1:
        raise ValueError("min_groups_for_performance_review must be a positive integer")
    pnl_tolerance = manifest.get("net_pnl_reconciliation_tolerance", 0.02)
    if not _finite_number(pnl_tolerance) or pnl_tolerance < 0:
        raise ValueError("net_pnl_reconciliation_tolerance must be finite and non-negative")
    results = [
        reconcile_report(item, min_groups=min_groups, pnl_tolerance=float(pnl_tolerance))
        for item in reports
    ]
    return {
        "schema_version": 1,
        "audit_type": "lona_tranche_vs_position_group_reconciliation",
        "optimization_allowed": all(r["optimization_allowed"] for r in results),
        "report_count": len(results),
        "history_reconciled_report_count": sum(r["history_reconciled"] for r in results),
        "unreconciled_report_count": sum(not r["history_reconciled"] for r in results),
        "promotion_blocked_report_count": sum(not r["optimization_allowed"] for r in results),
        "results": results,
        "rule": (
            "Reconcile tranche-level stored metrics against grouped position histories and the report's "
            "simulated commission; never mistake this for verified broker costs or use samples below "
            "the declared position-group threshold for optimization."
        ),
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
        "history_reconciled_report_count": result["history_reconciled_report_count"],
        "unreconciled_report_count": result["unreconciled_report_count"],
        "promotion_blocked_report_count": result["promotion_blocked_report_count"],
        "output": str(args.output),
    }, sort_keys=True))
    return 0 if result["optimization_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
