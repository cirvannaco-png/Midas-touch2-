#!/usr/bin/env python3
"""Outcome-linked, chronological research for Midas-touch2 order-flow diagnostics.

This is a descriptive research tool, not an optimizer or strategy promoter.
It consumes MT5 CSV exports and never fills missing realized outcomes with zero.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

EVIDENCE_REQUIRED = {
    "event_key", "symbol", "timeframe", "bar_end_epoch", "pressure_ratio",
    "bullish_sweep_reclaim", "bearish_sweep_reclaim",
    "absorption_proxy", "exhaustion_proxy",
}
SIGNAL_REQUIRED = {"SignalID", "Symbol", "EntryTF", "Direction"}
OUTCOME_REQUIRED = {"SignalID", "Filled", "RealizedR", "OutcomeEpoch"}
FEATURES = (
    "bullish_sweep_reclaim",
    "bearish_sweep_reclaim",
    "absorption_proxy",
    "exhaustion_proxy",
)


def read_csv(path: str | Path) -> list[dict[str, str]]:
    """Read comma- or semicolon-delimited MT5 exports, including UTF-8 BOM files."""
    p = Path(path)
    with p.open("r", newline="", encoding="utf-8-sig") as handle:
        sample = handle.read(8192)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(handle, dialect=dialect))
    if not rows:
        # An empty dataset has no usable header or evidence.
        raise ValueError(f"{p}: CSV has no data rows")
    return [{str(k).strip(): (v or "").strip() for k, v in row.items() if k is not None}
            for row in rows]


def require_columns(rows: list[dict[str, str]], needed: set[str], label: str) -> None:
    columns = set(rows[0])
    missing = sorted(needed - columns)
    if missing:
        raise ValueError(f"{label}: missing required columns: {', '.join(missing)}")


def parse_float(value: Any) -> float | None:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def parse_epoch(value: Any) -> int | None:
    number = parse_float(value)
    if number is None or number <= 0 or not number.is_integer():
        return None
    return int(number)


def parse_bool(value: Any) -> bool | None:
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None


def signal_epoch(signal_id: str) -> int | None:
    """SignalLogger IDs end in the canonical creation-time epoch."""
    suffix = signal_id.rsplit("_", 1)[-1]
    return parse_epoch(suffix)


def _dedupe_by_key(rows: Iterable[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "").strip()
        if not value:
            raise ValueError(f"{label}: empty {key}")
        old = indexed.get(value)
        if old is not None and old != row:
            raise ValueError(f"{label}: conflicting duplicate {key}={value}")
        indexed[value] = row
    return indexed


def load_order_flow_events(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    require_columns(rows, EVIDENCE_REQUIRED, "order-flow evidence")
    deduped = _dedupe_by_key(rows, "event_key", "order-flow evidence")
    events = []
    for event_key, row in deduped.items():
        end_epoch = parse_epoch(row.get("bar_end_epoch"))
        pressure = parse_float(row.get("pressure_ratio"))
        flags = {feature: parse_bool(row.get(feature)) for feature in FEATURES}
        if end_epoch is None or pressure is None or any(v is None for v in flags.values()):
            continue
        events.append({
            "event_key": event_key,
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "bar_end_epoch": end_epoch,
            "pressure_ratio": pressure,
            **flags,
        })
    return sorted(events, key=lambda e: (e["symbol"], e["timeframe"], e["bar_end_epoch"]))


def build_outcome_index(signal_rows: list[dict[str, str]],
                        outcome_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    require_columns(signal_rows, SIGNAL_REQUIRED, "signals")
    require_columns(outcome_rows, OUTCOME_REQUIRED, "outcomes")
    signals = _dedupe_by_key(signal_rows, "SignalID", "signals")
    outcomes = _dedupe_by_key(outcome_rows, "SignalID", "outcomes")
    index: dict[str, dict[str, Any]] = {}
    rejected = defaultdict(int)
    for signal_id, signal in signals.items():
        decision_epoch = signal_epoch(signal_id)
        if decision_epoch is None:
            rejected["invalid_signal_epoch"] += 1
            continue
        outcome = outcomes.get(signal_id)
        if outcome is None:
            rejected["unresolved_or_missing_outcome"] += 1
            continue
        if parse_bool(outcome.get("Filled")) is not True:
            rejected["not_filled"] += 1
            continue
        resolved_epoch = parse_epoch(outcome.get("OutcomeEpoch"))
        realized_r = parse_float(outcome.get("RealizedR"))
        if resolved_epoch is None or realized_r is None:
            rejected["invalid_or_missing_outcome_data"] += 1
            continue
        if resolved_epoch < decision_epoch:
            rejected["outcome_precedes_decision"] += 1
            continue
        index[signal_id] = {
            "signal_id": signal_id,
            "symbol": signal["Symbol"],
            "timeframe": signal["EntryTF"],
            "direction": signal["Direction"],
            "decision_epoch": decision_epoch,
            "resolved_epoch": resolved_epoch,
            "realized_r": realized_r,
        }
    for signal_id in outcomes.keys() - signals.keys():
        rejected["outcome_without_signal"] += 1
    return index, dict(rejected)


def join_events_to_outcomes(events: list[dict[str, Any]],
                            outcomes: dict[str, dict[str, Any]],
                            max_match_gap_seconds: int = 120) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if max_match_gap_seconds < 0:
        raise ValueError("max_match_gap_seconds must be non-negative")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[(event["symbol"], event["timeframe"])].append(event)
    joined: list[dict[str, Any]] = []
    rejected = defaultdict(int)
    for signal_id, outcome in outcomes.items():
        possible = grouped.get((outcome["symbol"], outcome["timeframe"]), [])
        eligible = [e for e in possible if e["bar_end_epoch"] <= outcome["decision_epoch"]]
        if not eligible:
            rejected["no_prior_same_symbol_timeframe_event"] += 1
            continue
        event = max(eligible, key=lambda e: e["bar_end_epoch"])
        gap = outcome["decision_epoch"] - event["bar_end_epoch"]
        if gap > max_match_gap_seconds:
            rejected["stale_event_for_signal"] += 1
            continue
        row = dict(outcome)
        row.update({name: event[name] for name in FEATURES})
        row["pressure_ratio"] = event["pressure_ratio"]
        row["event_key"] = event["event_key"]
        row["event_gap_seconds"] = gap
        joined.append(row)
    return sorted(joined, key=lambda r: r["decision_epoch"]), dict(rejected)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["realized_r"]) for row in rows
              if parse_float(row.get("realized_r")) is not None]
    if not values:
        return {
            "n": 0, "wins": 0, "losses": 0, "scratches": 0,
            "win_rate": None, "expectancy_r": None, "profit_factor": None,
            "max_drawdown_r": None, "total_r": 0.0,
        }
    wins = sum(v > 0 for v in values)
    losses = sum(v < 0 for v in values)
    scratches = sum(v == 0 for v in values)
    gross_profit = sum(v for v in values if v > 0)
    gross_loss = -sum(v for v in values if v < 0)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return {
        "n": len(values),
        "wins": wins,
        "losses": losses,
        "scratches": scratches,
        "win_rate": wins / len(values),
        "expectancy_r": sum(values) / len(values),
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "max_drawdown_r": max_drawdown,
        "total_r": sum(values),
    }


def chronological_split(rows: list[dict[str, Any]], holdout_fraction: float) -> dict[str, Any]:
    """Chronological holdout with purging: training outcomes must resolve before test starts."""
    if not 0.10 <= holdout_fraction <= 0.50:
        raise ValueError("holdout_fraction must be between 0.10 and 0.50")
    ordered = sorted(rows, key=lambda r: r["decision_epoch"])
    if len(ordered) < 2:
        return {"test_start_epoch": None, "train": [], "test": [], "purged_train": 0}
    cut = max(1, min(len(ordered) - 1, int(len(ordered) * (1.0 - holdout_fraction))))
    test_start = ordered[cut]["decision_epoch"]
    raw_train = [r for r in ordered if r["decision_epoch"] < test_start]
    train = [r for r in raw_train if r["resolved_epoch"] < test_start]
    test = [r for r in ordered if r["decision_epoch"] >= test_start]
    return {
        "test_start_epoch": test_start,
        "train": train,
        "test": test,
        "purged_train": len(raw_train) - len(train),
    }


def _groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {"all": rows}
    for feature in FEATURES:
        for value in (True, False):
            groups[f"{feature}={str(value).lower()}"] = [r for r in rows if r[feature] is value]
    for bucket, predicate in (
        ("pressure=positive", lambda p: p >= 0.15),
        ("pressure=neutral", lambda p: -0.15 < p < 0.15),
        ("pressure=negative", lambda p: p <= -0.15),
    ):
        groups[bucket] = [r for r in rows if predicate(r["pressure_ratio"])]
    return groups


def analyze(evidence_rows: list[dict[str, str]],
            signal_rows: list[dict[str, str]],
            outcome_rows: list[dict[str, str]],
            max_match_gap_seconds: int = 120,
            holdout_fraction: float = 0.30,
            min_sample: int = 30) -> dict[str, Any]:
    if min_sample < 1:
        raise ValueError("min_sample must be positive")
    events = load_order_flow_events(evidence_rows)
    outcome_index, outcome_rejections = build_outcome_index(signal_rows, outcome_rows)
    joined, join_rejections = join_events_to_outcomes(events, outcome_index, max_match_gap_seconds)
    split = chronological_split(joined, holdout_fraction)
    descriptions = {}
    for name, subset in _groups(joined).items():
        descriptions[name] = {
            "all_sample": summarize(subset),
            "train_sample": summarize([r for r in subset if r in split["train"]]),
            "holdout_sample": summarize([r for r in subset if r in split["test"]]),
            "sufficient_sample_for_descriptive_review": len(subset) >= min_sample,
        }
    return {
        "schema_version": "midas-touch2-order-flow-research-v1",
        "purpose": "descriptive diagnostics; not an execution policy or profitability claim",
        "matched_outcomes": len(joined),
        "source_event_count": len(events),
        "source_signal_count": len(signal_rows),
        "resolved_candidate_count": len(outcome_index),
        "outcome_rejections": outcome_rejections,
        "join_rejections": join_rejections,
        "chronological_holdout": {
            "test_start_epoch": split["test_start_epoch"],
            "train_count_after_purge": len(split["train"]),
            "holdout_count": len(split["test"]),
            "purged_training_rows": split["purged_train"],
            "train_metrics": summarize(split["train"]),
            "holdout_metrics": summarize(split["test"]),
        },
        "feature_breakdown": descriptions,
        "release_policy": {
            "automatic_promotion": False,
            "minimum_sample_is_not_proof_of_edge": True,
            "require_cost_aware_independent_validation": True,
            "require_demo_forward_review": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, help="Order-flow evidence CSV export")
    parser.add_argument("--signals", required=True, help="MedisTouch_Signals_<symbol>.csv export")
    parser.add_argument("--outcomes", required=True, help="MedisTouch_Outcomes_v2_<symbol>.csv export")
    parser.add_argument("--output", default="order_flow_research_report.json")
    parser.add_argument("--max-match-gap-seconds", type=int, default=120)
    parser.add_argument("--holdout-fraction", type=float, default=0.30)
    parser.add_argument("--min-sample", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        report = analyze(
            read_csv(args.evidence), read_csv(args.signals), read_csv(args.outcomes),
            max_match_gap_seconds=args.max_match_gap_seconds,
            holdout_fraction=args.holdout_fraction,
            min_sample=args.min_sample,
        )
        Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"order_flow_research: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "matched_outcomes": report["matched_outcomes"],
        "train_count": report["chronological_holdout"]["train_count_after_purge"],
        "holdout_count": report["chronological_holdout"]["holdout_count"],
        "report": str(Path(args.output)),
        "automatic_promotion": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
