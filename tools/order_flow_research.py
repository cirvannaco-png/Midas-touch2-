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
    "schema_version", "event_key", "symbol", "timeframe", "bar_end_epoch", "pressure_ratio",
    "diagnostic_status",
    "bullish_sweep_reclaim", "bearish_sweep_reclaim",
    "absorption_proxy", "exhaustion_proxy", "data_quality", "data_stale",
}
SIGNAL_REQUIRED = {"SignalID", "Symbol", "EntryTF", "Direction"}
OUTCOME_REQUIRED = {"SignalID", "Filled", "RealizedR", "OutcomeEpoch"}
ATTRIBUTION_REQUIRED = {
    "schema_version", "signal_id", "event_key", "symbol", "timeframe",
    "direction", "signal_epoch", "attribution_status",
}
ATTRIBUTION_V2_REQUIRED = {"decision_id", "decision_fingerprint"}
ATTRIBUTION_V3_REQUIRED = {
    "smc_inducement_valid", "smc_liquidity_swept", "smc_bos_confirmed",
    "smc_sweep_grade", "smc_bos_strength", "smc_time_decay",
}
FEATURES = (
    "bullish_sweep_reclaim",
    "bearish_sweep_reclaim",
    "absorption_proxy",
    "exhaustion_proxy",
)

TIMEFRAME_SECONDS = {
    "PERIOD_M1": 60, "PERIOD_M2": 120, "PERIOD_M3": 180,
    "PERIOD_M4": 240, "PERIOD_M5": 300, "PERIOD_M6": 360,
    "PERIOD_M10": 600, "PERIOD_M12": 720, "PERIOD_M15": 900,
    "PERIOD_M20": 1200, "PERIOD_M30": 1800, "PERIOD_H1": 3600,
    "PERIOD_H2": 7200, "PERIOD_H3": 10800, "PERIOD_H4": 14400,
    "PERIOD_H6": 21600, "PERIOD_H8": 28800, "PERIOD_H12": 43200,
    "PERIOD_D1": 86400, "PERIOD_W1": 604800,
}


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
    if not rows:
        raise ValueError(f"{label}: no data rows")
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


def _is_unit_interval(value: Any) -> bool:
    """Return true only for finite numeric values normalized to the [0, 1] range."""
    number = parse_float(value)
    return number is not None and 0.0 <= number <= 1.0


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


def load_order_flow_events(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    require_columns(rows, EVIDENCE_REQUIRED, "order-flow evidence")
    deduped = _dedupe_by_key(rows, "event_key", "order-flow evidence")
    events = []
    rejected = defaultdict(int)
    for event_key, row in deduped.items():
        schema_version = row.get("schema_version")
        if schema_version not in {"order-flow-evidence-v2", "order-flow-evidence-v3"}:
            rejected["unsupported_schema_version"] += 1
            continue
        if schema_version == "order-flow-evidence-v3":
            v3_required = {
                "signed_tick_pressure", "positive_tick_count", "negative_tick_count",
                "price_progress", "prior_high", "prior_low", "bar_close", "atr",
                "pressure_progress_divergence", "continuation_hypothesis", "reversal_hypothesis",
                "auction_context_available", "value_area_poc", "value_area_vah", "value_area_val",
                "value_area_source_quality", "value_area_source", "auction_location",
            }
            if any(name not in row for name in v3_required):
                rejected["incomplete_v3_schema"] += 1
                continue
        end_epoch = parse_epoch(row.get("bar_end_epoch"))
        pressure = parse_float(row.get("pressure_ratio"))
        quality = parse_epoch(row.get("data_quality"))
        stale = parse_bool(row.get("data_stale"))
        status = row.get("diagnostic_status", "").strip().upper()
        flags = {feature: parse_bool(row.get(feature)) for feature in FEATURES}
        if (end_epoch is None or pressure is None or stale is None or not status or
                any(v is None for v in flags.values())):
            rejected["invalid_event_fields"] += 1
            continue
        # Failed windows are retained in the CSV so report coverage can show
        # them, but only complete, non-stale proxy observations enter metrics.
        if status == "STALE_PROXY" or (status == "OK_PROXY" and stale):
            rejected["stale_event_record"] += 1
            continue
        if status != "OK_PROXY":
            rejected["status_" + status.lower()] += 1
            continue
        if quality != 1:
            rejected["unsupported_or_mislabeled_data_quality"] += 1
            continue
        numeric_fields = (
            "signed_tick_pressure", "positive_tick_count", "negative_tick_count",
            "price_progress", "prior_high", "prior_low", "bar_close", "atr",
            "value_area_poc", "value_area_vah", "value_area_val", "value_area_source_quality",
            "value_area_source", "auction_location", "continuation_hypothesis", "reversal_hypothesis",
        )
        parsed_numeric = {name: parse_float(row.get(name)) for name in numeric_fields}
        parsed_divergence = parse_bool(row.get("pressure_progress_divergence"))
        auction_available = parse_bool(row.get("auction_context_available"))
        if schema_version == "order-flow-evidence-v3" and (
                parsed_divergence is None or auction_available is None or
                any(parsed_numeric[name] is None for name in (
                    "signed_tick_pressure", "positive_tick_count", "negative_tick_count",
                    "price_progress", "prior_high", "prior_low", "bar_close", "atr",
                    "value_area_source_quality", "value_area_source", "auction_location",
                    "continuation_hypothesis", "reversal_hypothesis"))):
            rejected["invalid_v3_event_fields"] += 1
            continue
        events.append({
            "event_key": event_key,
            "schema_version": schema_version,
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "bar_end_epoch": end_epoch,
            "pressure_ratio": pressure,
            "pressure_progress_divergence": parsed_divergence,
            "auction_context_available": auction_available,
            **parsed_numeric,
            **flags,
        })
    return sorted(events, key=lambda e: (e["symbol"], e["timeframe"], e["bar_end_epoch"])), dict(rejected)


def _annotate_order_flow_proxies(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add descriptive, no-look-ahead tags; these are not execution signals.

    The cumulative pressure proxy resets at UTC-day boundaries and after a
    missing-bar-sized gap. It accumulates up/down midpoint-change COUNTS, not
    traded volume. It must never be described as exchange CVD.
    """
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[(event["symbol"], event["timeframe"], event["bar_end_epoch"] // 86400)].append(event)

    annotated = []
    for key in sorted(grouped):
        series = sorted(grouped[key], key=lambda e: (e["bar_end_epoch"], e["event_key"]))
        tf_seconds = TIMEFRAME_SECONDS.get(key[1])
        cumulative_signed = 0.0
        cumulative_directional = 0.0
        first_close: float | None = None
        previous_epoch: int | None = None
        have_counts = False
        for event in series:
            epoch = event["bar_end_epoch"]
            if (previous_epoch is not None and tf_seconds is not None and
                    epoch - previous_epoch > tf_seconds):
                cumulative_signed = 0.0
                cumulative_directional = 0.0
                first_close = None
                have_counts = False

            signed = event.get("signed_tick_pressure")
            positive = event.get("positive_tick_count")
            negative = event.get("negative_tick_count")
            if signed is not None and positive is not None and negative is not None:
                cumulative_signed += float(signed)
                cumulative_directional += max(0.0, float(positive)) + max(0.0, float(negative))
                have_counts = True
            event["utc_day_cumulative_tick_pressure_proxy"] = cumulative_signed if have_counts else None
            event["utc_day_cumulative_pressure_ratio_proxy"] = (
                cumulative_signed / cumulative_directional
                if have_counts and cumulative_directional > 0.0 else None
            )

            close = event.get("bar_close")
            atr = event.get("atr")
            if close is not None:
                if first_close is None:
                    first_close = float(close)
                event["utc_day_price_change"] = float(close) - first_close
            else:
                event["utc_day_price_change"] = None

            ratio = event["utc_day_cumulative_pressure_ratio_proxy"]
            price_change = event["utc_day_price_change"]
            event["utc_day_pressure_price_divergence"] = (
                bool(abs(float(ratio)) >= 0.20 and
                     abs(float(price_change)) >= max(1e-12, 0.25 * float(atr)) and
                     ((float(ratio) > 0.0 and float(price_change) < 0.0) or
                      (float(ratio) < 0.0 and float(price_change) > 0.0)))
                if ratio is not None and price_change is not None and atr is not None else None
            )

            if event.get("pressure_progress_divergence") is None:
                pressure = float(event["pressure_ratio"])
                progress = event.get("price_progress")
                event["pressure_progress_divergence"] = (
                    bool((pressure >= 0.60 and float(progress) < 0.0) or
                         (pressure <= -0.60 and float(progress) > 0.0))
                    if progress is not None else None
                )

            if event.get("auction_context_available") is True:
                location = event.get("auction_location")
                event["auction_location_label"] = {
                    -2.0: "BELOW_VAL", -1.0: "IN_VALUE_BELOW_POC", 0.0: "NEAR_POC",
                    1.0: "IN_VALUE_ABOVE_POC", 2.0: "ABOVE_VAH",
                }.get(location, "UNCLASSIFIED")
            else:
                event["auction_location_label"] = "UNAVAILABLE"

            for field in ("continuation_hypothesis", "reversal_hypothesis"):
                raw = event.get(field)
                event[field + "_label"] = (
                    "BULLISH" if raw is not None and float(raw) > 0 else
                    "BEARISH" if raw is not None and float(raw) < 0 else
                    "NONE" if raw is not None else "NOT_RECORDED"
                )
            previous_epoch = epoch
            annotated.append(event)
    return sorted(annotated, key=lambda e: (e["symbol"], e["timeframe"], e["bar_end_epoch"]))


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
            "session": signal.get("Session", "").strip(),
            "regime": signal.get("Regime", "").strip(),
            "volatility_regime": signal.get("VolRegime", "").strip(),
            "selected_strategy": signal.get("SelectedStrategy", "").strip(),
            "decision_epoch": decision_epoch,
            "resolved_epoch": resolved_epoch,
            "realized_r": realized_r,
        }
    for signal_id in outcomes.keys() - signals.keys():
        rejected["outcome_without_signal"] += 1
    return index, dict(rejected)



def build_attribution_index(rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, int]]:
    """Index explicit signal-to-event links. Never fall back to time for supplied attribution."""
    require_columns(rows, ATTRIBUTION_REQUIRED, "order-flow attribution")
    indexed_rows = _dedupe_by_key(rows, "signal_id", "order-flow attribution")
    index: dict[str, dict[str, str]] = {}
    rejected = defaultdict(int)
    for signal_id, row in indexed_rows.items():
        status = row.get("attribution_status", "").strip().upper()
        schema = row.get("schema_version", "").strip()
        if schema not in {"order-flow-attribution-v1", "order-flow-attribution-v2", "order-flow-attribution-v3"}:
            rejected["unsupported_attribution_schema"] += 1
        elif status != "MATCHED":
            rejected["status_" + (status.lower() if status else "missing")] += 1
        elif not row.get("event_key", "").strip():
            rejected["matched_status_without_event_key"] += 1
        elif schema in {"order-flow-attribution-v2", "order-flow-attribution-v3"} and (
                not ATTRIBUTION_V2_REQUIRED.issubset(row) or
                not row.get("decision_id", "").strip().isdecimal() or
                int(row.get("decision_id", "0") or "0") <= 0 or
                not row.get("decision_fingerprint", "").strip()):
            rejected["missing_decision_lineage"] += 1
        elif schema == "order-flow-attribution-v3" and (
                not ATTRIBUTION_V3_REQUIRED.issubset(row) or
                any(parse_bool(row.get(field)) is None for field in (
                    "smc_inducement_valid", "smc_liquidity_swept", "smc_bos_confirmed")) or
                row.get("smc_sweep_grade", "").strip().upper() not in {
                    "SWEEP_GRADE_NONE", "SWEEP_GRADE_C", "SWEEP_GRADE_B", "SWEEP_GRADE_A"} or
                parse_float(row.get("smc_bos_strength")) is None or
                parse_float(row.get("smc_time_decay")) is None):
            rejected["invalid_smc_context"] += 1
        else:
            index[signal_id] = row
    return index, dict(rejected)


def join_events_to_outcomes(events: list[dict[str, Any]],
                            outcomes: dict[str, dict[str, Any]],
                            max_match_gap_seconds: int | None = None,
                            attribution_index: dict[str, dict[str, str]] | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if max_match_gap_seconds is not None and max_match_gap_seconds < 0:
        raise ValueError("max_match_gap_seconds must be non-negative")
    if max_match_gap_seconds == 0:
        raise ValueError("max_match_gap_seconds must be positive when explicitly set")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[(event["symbol"], event["timeframe"])].append(event)
    joined: list[dict[str, Any]] = []
    rejected = defaultdict(int)
    events_by_key = {event["event_key"]: event for event in events}
    for signal_id, outcome in outcomes.items():
        possible = grouped.get((outcome["symbol"], outcome["timeframe"]), [])
        if attribution_index is not None:
            attribution = attribution_index.get(signal_id)
            if attribution is None:
                rejected["missing_direct_attribution"] += 1
                continue
            if (attribution.get("symbol") != outcome["symbol"] or
                    attribution.get("timeframe") != outcome["timeframe"] or
                    attribution.get("direction") != outcome["direction"] or
                    parse_epoch(attribution.get("signal_epoch")) != outcome["decision_epoch"]):
                rejected["attribution_identity_mismatch"] += 1
                continue
            event = events_by_key.get(attribution.get("event_key", "").strip())
            if event is None:
                rejected["direct_event_unusable_or_missing"] += 1
                continue
            if event["symbol"] != outcome["symbol"] or event["timeframe"] != outcome["timeframe"]:
                rejected["direct_event_identity_mismatch"] += 1
                continue
            if event["bar_end_epoch"] > outcome["decision_epoch"]:
                rejected["direct_attribution_event_after_signal"] += 1
                continue
        else:
            eligible = [e for e in possible if e["bar_end_epoch"] <= outcome["decision_epoch"]]
            if not eligible:
                rejected["no_prior_same_symbol_timeframe_event"] += 1
                continue
            event = max(eligible, key=lambda e: e["bar_end_epoch"])
        gap = outcome["decision_epoch"] - event["bar_end_epoch"]
        timeframe_limit = TIMEFRAME_SECONDS.get(outcome["timeframe"])
        if max_match_gap_seconds is None:
            if timeframe_limit is None:
                rejected["unsupported_timeframe_for_default_match_window"] += 1
                continue
            match_limit = timeframe_limit
        else:
            match_limit = max_match_gap_seconds
        if gap > match_limit:
            rejected["stale_event_for_signal"] += 1
            continue
        row = dict(outcome)
        row.update({name: event[name] for name in FEATURES})
        row["pressure_ratio"] = event["pressure_ratio"]
        for name in (
            "pressure_progress_divergence", "utc_day_cumulative_tick_pressure_proxy",
            "utc_day_cumulative_pressure_ratio_proxy", "utc_day_price_change",
            "utc_day_pressure_price_divergence", "auction_location_label",
            "continuation_hypothesis_label", "reversal_hypothesis_label",
        ):
            row[name] = event.get(name)
        row["event_key"] = event["event_key"]
        row["event_gap_seconds"] = gap
        if attribution_index is not None and attribution is not None:
            # Keep exact decision lineage in the report when using v2/v3 schemas.
            row["decision_id"] = attribution.get("decision_id")
            row["decision_fingerprint"] = attribution.get("decision_fingerprint")
            if attribution.get("schema_version") == "order-flow-attribution-v3":
                for field in ("smc_inducement_valid", "smc_liquidity_swept", "smc_bos_confirmed"):
                    row[field] = parse_bool(attribution.get(field))
                row["smc_sweep_grade"] = attribution.get("smc_sweep_grade")
                row["smc_bos_strength"] = parse_float(attribution.get("smc_bos_strength"))
                row["smc_time_decay"] = parse_float(attribution.get("smc_time_decay"))
        joined.append(row)
    return sorted(joined, key=lambda r: r["decision_epoch"]), dict(rejected)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_rows = [
        (index, row, parse_float(row.get("realized_r")))
        for index, row in enumerate(rows)
        if parse_float(row.get("realized_r")) is not None
    ]
    # Equity drawdown must follow when trades actually resolve, not signal time:
    # overlapping positions can close in a different order from their entries.
    if valid_rows and all(parse_epoch(row.get("resolved_epoch")) is not None
                          for _, row, _ in valid_rows):
        valid_rows.sort(key=lambda item: (
            parse_epoch(item[1].get("resolved_epoch")),
            parse_epoch(item[1].get("decision_epoch")) or 0,
            item[0],
        ))
    values = [float(value) for _, _, value in valid_rows]
    if not values:
        return {
            "n": 0, "trade_count": 0, "wins": 0, "losses": 0, "scratches": 0,
            "win_rate": None, "expectancy_r": None, "profit_factor": None,
            "max_drawdown_r": None, "total_r": 0.0,
            "longest_loss_streak": 0, "longest_win_streak": 0,
            "observed_calendar_days": None, "trades_per_30_calendar_days": None,
        }
    wins = sum(v > 0 for v in values)
    losses = sum(v < 0 for v in values)
    scratches = sum(v == 0 for v in values)
    gross_profit = sum(v for v in values if v > 0)
    gross_loss = -sum(v for v in values if v < 0)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    current_loss_streak = 0
    current_win_streak = 0
    longest_loss_streak = 0
    longest_win_streak = 0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        if value < 0:
            current_loss_streak += 1
            current_win_streak = 0
        elif value > 0:
            current_win_streak += 1
            current_loss_streak = 0
        else:
            # Scratches break both runs; do not silently count a flat as a win/loss.
            current_loss_streak = 0
            current_win_streak = 0
        longest_loss_streak = max(longest_loss_streak, current_loss_streak)
        longest_win_streak = max(longest_win_streak, current_win_streak)

    epochs = [parse_epoch(row.get("decision_epoch")) for _, row, _ in valid_rows]
    observed_days = None
    trades_per_30_days = None
    if epochs and all(epoch is not None for epoch in epochs):
        span_seconds = max(epochs) - min(epochs)
        if span_seconds > 0:
            observed_days = span_seconds / 86400.0
            trades_per_30_days = len(values) * 30.0 / observed_days
    return {
        "n": len(values),
        "trade_count": len(values),
        "wins": wins,
        "losses": losses,
        "scratches": scratches,
        "win_rate": wins / len(values),
        "expectancy_r": sum(values) / len(values),
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "max_drawdown_r": max_drawdown,
        "total_r": sum(values),
        "longest_loss_streak": longest_loss_streak,
        "longest_win_streak": longest_win_streak,
        "observed_calendar_days": observed_days,
        "trades_per_30_calendar_days": trades_per_30_days,
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

    def category_text(value: Any) -> str:
        # Canonicalize booleans to lower-case so JSON reports and stable keys
        # do not depend on whether inputs came from Python bools or CSV text.
        if isinstance(value, bool):
            return str(value).lower()
        return str(value if value is not None else "").strip()

    for feature in FEATURES:
        for value in (True, False):
            groups[f"{feature}={str(value).lower()}"] = [r for r in rows if r[feature] is value]
    for bucket, predicate in (
        ("pressure=positive", lambda p: p >= 0.15),
        ("pressure=neutral", lambda p: -0.15 < p < 0.15),
        ("pressure=negative", lambda p: p <= -0.15),
    ):
        groups[bucket] = [r for r in rows if predicate(r["pressure_ratio"])]
    # Context stratification is descriptive, not a vote or an auto-promotion
    # rule. Missing labels are omitted rather than imputed.
    for dimension in ("direction", "symbol", "timeframe", "session", "regime",
                      "volatility_regime", "selected_strategy", "auction_location_label",
                      "continuation_hypothesis_label", "reversal_hypothesis_label",
                      "pressure_progress_divergence", "utc_day_pressure_price_divergence",
                      "smc_inducement_valid", "smc_liquidity_swept", "smc_bos_confirmed",
                      "smc_sweep_grade"):
        categories = sorted({category_text(r.get(dimension))
                             for r in rows if category_text(r.get(dimension))})
        for category in categories:
            groups[f"{dimension}={category}"] = [
                r for r in rows if category_text(r.get(dimension)) == category
            ]
    return groups


def analyze(evidence_rows: list[dict[str, str]],
            signal_rows: list[dict[str, str]],
            outcome_rows: list[dict[str, str]],
            max_match_gap_seconds: int | None = None,
            holdout_fraction: float = 0.30,
            min_sample: int = 30,
            attribution_rows: list[dict[str, str]] | None = None) -> dict[str, Any]:
    if min_sample < 1:
        raise ValueError("min_sample must be positive")
    events, event_rejections = load_order_flow_events(evidence_rows)
    events = _annotate_order_flow_proxies(events)
    raw_event_keys = {row.get("event_key", "").strip() for row in evidence_rows
                      if row.get("event_key", "").strip()}
    outcome_index, outcome_rejections = build_outcome_index(signal_rows, outcome_rows)
    attribution_rejections: dict[str, int] = {}
    attribution_mode = "nearest_prior_time"
    attribution_index = None
    if attribution_rows is not None:
        attribution_mode = "direct_signal_id"
        attribution_index, attribution_rejections = build_attribution_index(attribution_rows)
    joined, join_rejections = join_events_to_outcomes(
        events, outcome_index, max_match_gap_seconds, attribution_index
    )
    split = chronological_split(joined, holdout_fraction)
    descriptions = {}
    for name, subset in _groups(joined).items():
        unique_events = {r["event_key"] for r in subset}
        descriptions[name] = {
            "all_sample": summarize(subset),
            "train_sample": summarize([r for r in subset if r in split["train"]]),
            "holdout_sample": summarize([r for r in subset if r in split["test"]]),
            "unique_evidence_events": len(unique_events),
            "sufficient_unique_event_sample_for_descriptive_review": len(unique_events) >= min_sample,
            "note": "Trade rows sharing an event are correlated and are not independent evidence.",
        }
    unique_joined_events = {r["event_key"] for r in joined}
    event_counts: dict[str, int] = defaultdict(int)
    for row in joined:
        event_counts[row["event_key"]] += 1
    return {
        "schema_version": "midas-touch2-order-flow-research-v1",
        "purpose": "descriptive diagnostics; not an execution policy or profitability claim",
        "attribution_mode": attribution_mode,
        "attribution_rejections": attribution_rejections,
        "matched_outcomes": len(joined),
        "matched_unique_event_count": len(unique_joined_events),
        "signals_per_event": {
            "unique_event_count": len(event_counts),
            "max_signals_per_event": max(event_counts.values()) if event_counts else 0,
            "events_shared_by_multiple_signals": sum(n > 1 for n in event_counts.values()),
            "note": "Trade count is not the independent sample size when multiple signals share a bar feature snapshot.",
        },
        "source_evidence_row_count": len(evidence_rows),
        "distinct_evidence_event_keys": len(raw_event_keys),
        "source_event_count": len(events),
        "usable_evidence_fraction": (
            len(events) / len(raw_event_keys) if raw_event_keys else None
        ),
        "source_signal_count": len(signal_rows),
        "event_rejections": event_rejections,
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
    parser.add_argument(
        "--attribution", default=None,
        help="optional MedisTouch_OrderFlowAttribution_v1/v2/v3_<symbol>_<timeframe>.csv; direct SignalID join, no time fallback",
    )
    parser.add_argument("--output", default="order_flow_research_report.json")
    parser.add_argument(
        "--max-match-gap-seconds", type=int, default=None,
        help="override default match limit (one signal timeframe bar); must be positive",
    )
    parser.add_argument("--holdout-fraction", type=float, default=0.30)
    parser.add_argument("--min-sample", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        report = analyze(
            read_csv(args.evidence), read_csv(args.signals), read_csv(args.outcomes),
            max_match_gap_seconds=args.max_match_gap_seconds,
            holdout_fraction=args.holdout_fraction,
            min_sample=args.min_sample,
            attribution_rows=read_csv(args.attribution) if args.attribution else None,
        )
        Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"order_flow_research: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "matched_outcomes": report["matched_outcomes"],
        "attribution_mode": report["attribution_mode"],
        "train_count": report["chronological_holdout"]["train_count_after_purge"],
        "holdout_count": report["chronological_holdout"]["holdout_count"],
        "report": str(Path(args.output)),
        "automatic_promotion": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
