"""Walk-forward validation over real OutcomeTracker observations.

The module never reimplements EA signal logic. It analyses persisted
OutcomeTracker observations and can ingest an actual exported CSV when a
Strategy Tester run is available. The CSV parser is deliberately strict:
it requires a real header and a signal identifier/outcome pair and refuses
ambiguous files rather than guessing a tester schema.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
from _pathutil import ensure_bridge_importable  # noqa: E402
ensure_bridge_importable(__file__)

from sqlalchemy import select  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models import SignalOutcome  # noqa: E402
from metrics_engine import compute_report  # noqa: E402
from stats import intervals_overlap, wilson_ci  # noqa: E402
from instrument_taxonomy import classify_symbol
from oos_firewall import OOSPurityError, validate_records

RESOLVED_OUTCOMES = {"win", "loss", "scratch"}

def _oos_record(row) -> dict:
    fields = (
        "decision_id", "signal_id", "signal_time", "decision_time", "execution_time",
        "outcome_time", "data_received_time", "strategy_version", "model_version",
        "weight_version", "calibration_version", "feature_schema_version",
        "environment_schema_version", "decision_fingerprint", "original_decision_fingerprint",
        "strategy", "symbol", "asset_class", "filled", "commission_cost", "spread_cost",
        "slippage_cost", "source_type",
    )
    out = {}
    for field in fields:
        if isinstance(row, dict):
            out[field] = row.get(field)
        else:
            out[field] = getattr(row, field, None)
    if not out.get("signal_id"):
        out["signal_id"] = out.get("decision_id")
    if not out.get("decision_id"):
        out["decision_id"] = out.get("signal_id")
    if not out.get("asset_class") and out.get("symbol"):
        out["asset_class"] = classify_symbol(str(out["symbol"]))
    return out

def validate_locked_oos(rows) -> None:
    validate_records([_oos_record(r) for r in rows])



def _event_time(row) -> datetime | None:
    """Use signal creation time; outcome receipt is a legacy fallback."""
    return getattr(row, "signal_time", None) or getattr(row, "received_at", None)


def _filter_scope(rows, *, symbol: str | None = None, strategy: str | None = None):
    out = [r for r in rows if symbol is None or r.symbol == symbol]
    return [r for r in out if strategy is None or r.strategy == strategy]


def split_train_holdout(rows, reference_weeks: int = 4, holdout_weeks: int = 1,
                        now: datetime | None = None) -> tuple[list, list]:
    if reference_weeks <= holdout_weeks or holdout_weeks <= 0:
        raise ValueError("reference_weeks must be greater than holdout_weeks > 0")
    if now is None:
        now = max((_event_time(r) for r in rows if _event_time(r)), default=datetime.now(timezone.utc))
    reference_start = now - timedelta(weeks=reference_weeks)
    holdout_start = now - timedelta(weeks=holdout_weeks)
    train, holdout = [], []
    for r in rows:
        event_time = _event_time(r)
        if not event_time or event_time < reference_start:
            continue
        (holdout if event_time >= holdout_start else train).append(r)
    return train, holdout


def compute_walk_forward_report(rows, weight_version: str, reference_weeks: int = 4,
                                holdout_weeks: int = 1, *, symbol: str | None = None,
                                strategy: str | None = None) -> dict:
    tagged = _filter_scope([r for r in rows if r.weight_version == weight_version], symbol=symbol, strategy=strategy)
    train, holdout = split_train_holdout(tagged, reference_weeks, holdout_weeks)
    train_resolved = [r for r in train if r.outcome in RESOLVED_OUTCOMES]
    holdout_resolved = [r for r in holdout if r.outcome in RESOLVED_OUTCOMES]
    train_ci = wilson_ci(sum(1 for r in train_resolved if r.outcome == "win"), len(train_resolved))
    holdout_ci = wilson_ci(sum(1 for r in holdout_resolved if r.outcome == "win"), len(holdout_resolved))
    overlap = intervals_overlap(train_ci, holdout_ci)
    return {
        "weight_version": weight_version,
        "reference_weeks": reference_weeks,
        "holdout_weeks": holdout_weeks,
        "symbol": symbol,
        "asset_class": classify_symbol(symbol) if symbol else "multi_asset",
        "strategy": strategy,
        "time_basis": "signal_time_with_received_at_legacy_fallback",
        "train": compute_report(train) if train else None,
        "holdout": compute_report(holdout) if holdout else None,
        "train_win_rate_ci": train_ci.to_dict(),
        "holdout_win_rate_ci": holdout_ci.to_dict(),
        "overlap": overlap,
        "verdict": "insufficient_data" if overlap is None else ("consistent" if overlap else "diverged"),
    }




def compute_rolling_walk_forward_report(rows, weight_version: str, train_weeks: int = 4,
                                        holdout_weeks: int = 1, step_weeks: int = 1,
                                        folds: int = 3, *, symbol: str | None = None,
                                        strategy: str | None = None) -> dict:
    """Run multiple chronological train/holdout folds without future leakage."""
    if train_weeks <= 0 or holdout_weeks <= 0 or step_weeks <= 0 or folds <= 0:
        raise ValueError("train_weeks, holdout_weeks, step_weeks, and folds must be > 0")
    tagged = _filter_scope([r for r in rows if r.weight_version == weight_version], symbol=symbol, strategy=strategy)
    events = [(r, _event_time(r)) for r in tagged if _event_time(r) is not None]
    if not events:
        return {"weight_version": weight_version, "folds": [], "verdict": "insufficient_data", "time_basis": "signal_time_with_received_at_legacy_fallback", "symbol": symbol, "asset_class": classify_symbol(symbol) if symbol else "multi_asset", "strategy": strategy}
    start = min(t for _, t in events)
    end = max(t for _, t in events)
    train_delta = timedelta(weeks=train_weeks)
    holdout_delta = timedelta(weeks=holdout_weeks)
    step_delta = timedelta(weeks=step_weeks)
    reports = []
    cursor = start
    while cursor + train_delta + holdout_delta <= end and len(reports) < folds:
        train_end = cursor + train_delta
        holdout_end = train_end + holdout_delta
        train = [r for r, t in events if cursor <= t < train_end]
        holdout = [r for r, t in events if train_end <= t < holdout_end]
        if train and holdout:
            train_resolved = [r for r in train if r.outcome in RESOLVED_OUTCOMES]
            holdout_resolved = [r for r in holdout if r.outcome in RESOLVED_OUTCOMES]
            train_ci = wilson_ci(sum(r.outcome == "win" for r in train_resolved), len(train_resolved))
            holdout_ci = wilson_ci(sum(r.outcome == "win" for r in holdout_resolved), len(holdout_resolved))
            overlap = intervals_overlap(train_ci, holdout_ci)
            reports.append({
                "train_start": cursor.isoformat(), "train_end": train_end.isoformat(),
                "holdout_start": train_end.isoformat(), "holdout_end": holdout_end.isoformat(),
                "train_count": len(train), "holdout_count": len(holdout),
                "train_win_rate_ci": train_ci.to_dict(), "holdout_win_rate_ci": holdout_ci.to_dict(),
                "overlap": overlap,
                "verdict": "insufficient_data" if overlap is None else ("consistent" if overlap else "diverged"),
                "train_max_signal_time": max(_event_time(r) for r in train).isoformat(),
                "holdout_min_signal_time": min(_event_time(r) for r in holdout).isoformat(),
            })
        cursor += step_delta
    verdict = "insufficient_data" if not reports else ("diverged" if any(f["verdict"] == "diverged" for f in reports) else ("insufficient_data" if any(f["verdict"] == "insufficient_data" for f in reports) else "consistent"))
    return {"weight_version": weight_version, "train_weeks": train_weeks, "holdout_weeks": holdout_weeks, "step_weeks": step_weeks, "symbol": symbol, "asset_class": classify_symbol(symbol) if symbol else "multi_asset", "strategy": strategy, "time_basis": "signal_time_with_received_at_legacy_fallback", "folds": reports, "verdict": verdict}

def _pick(row: dict[str, str], aliases: tuple[str, ...], required: bool = False) -> str | None:
    normalized = {k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in row.items()}
    for alias in aliases:
        value = normalized.get(alias)
        if value not in (None, ""):
            return value
    if required:
        raise ValueError(f"tester CSV is missing required column/value; expected one of {aliases}")
    return None


def ingest_tester_csv(path: str) -> list[dict]:
    """Parse a real tester/OutcomeTracker CSV without guessing its schema.

    Required columns: ``signal_id`` (or ``decision_id``) and ``outcome``.
    Optional fields are normalized when present. Unknown columns are retained
    in ``raw`` so the import remains lossless for later analysis.
    """
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("tester CSV has no header; refusing to infer a schema")
        rows: list[dict] = []
        for line_no, raw in enumerate(reader, start=2):
            signal_id = _pick(raw, ("signal_id", "decision_id"), required=True)
            outcome = _pick(raw, ("outcome", "result"), required=True)
            outcome = outcome.lower()
            if outcome not in RESOLVED_OUTCOMES:
                raise ValueError(f"line {line_no}: unsupported outcome '{outcome}'")
            realized = _pick(raw, ("realized_r", "realized_r_multiple", "r_multiple"))
            try:
                realized_r = float(realized) if realized is not None else None
            except ValueError as exc:
                raise ValueError(f"line {line_no}: invalid realized_r '{realized}'") from exc
            rows.append({
                "signal_id": signal_id,
                "outcome": outcome,
                "realized_r": realized_r,
                "regime": _pick(raw, ("regime",)),
                "session": _pick(raw, ("session",)),
                "strategy": _pick(raw, ("strategy",)),
                "weight_version": _pick(raw, ("weight_version", "weights", "weight_set")),
                "received_at": _pick(raw, ("received_at", "creation_time", "created_at")),
                "raw": dict(raw),
            })
    return rows


def print_walk_forward(report: dict) -> None:
    print("=" * 88)
    if "folds" in report:
        print(f"ROLLING WALK-FORWARD — {report['weight_version']} ({len(report['folds'])} folds)")
        print("=" * 88)
        print(f"Verdict: {report['verdict']}")
        for i, fold in enumerate(report["folds"], start=1):
            print(
                f"Fold {i}: train={fold['train_count']} holdout={fold['holdout_count']} "
                f"verdict={fold['verdict']} train_max={fold['train_max_signal_time']} "
                f"holdout_min={fold['holdout_min_signal_time']}"
            )
        return
    print(f"WALK-FORWARD VALIDATION — {report['weight_version']} ({report['reference_weeks']}W reference, last {report['holdout_weeks']}W holdout)")
    print("=" * 88)
    print(f"Verdict: {report['verdict']}")
    print(f"Train win rate:   {_fmt_ci(report['train_win_rate_ci'])}")
    print(f"Holdout win rate: {_fmt_ci(report['holdout_win_rate_ci'])}")


def _fmt_ci(d: dict) -> str:
    if d.get("value") is None:
        return f"n/a (n={d.get('n', 0)})"
    return f"{d['value']*100:.1f}% [{d['ci_low']*100:.1f}%, {d['ci_high']*100:.1f}%] (n={d['n']})"


async def run(args) -> int:
    async with async_session() as session:
        result = await session.execute(select(SignalOutcome))
        rows = list(result.scalars().all())
    if not rows:
        print("walk_forward: no rows in signal_outcomes yet.", file=sys.stderr)
        return 1
    if args.certification_mode:
        try:
            validate_locked_oos(rows)
        except OOSPurityError as exc:
            print(f"walk_forward: OOS purity firewall rejected dataset: {exc}", file=sys.stderr)
            return 2
    if args.rolling:
        report = compute_rolling_walk_forward_report(rows, args.weight_version, args.reference_weeks, args.holdout_weeks, args.step_weeks, args.folds, symbol=args.symbol, strategy=args.strategy)
    else:
        report = compute_walk_forward_report(rows, args.weight_version, args.reference_weeks, args.holdout_weeks, symbol=args.symbol, strategy=args.strategy)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_walk_forward(report)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Walk-forward validation over persisted EA outcomes")
    parser.add_argument("--weight-version", required=True)
    parser.add_argument("--reference-weeks", type=int, default=4)
    parser.add_argument("--holdout-weeks", type=int, default=1)
    parser.add_argument("--tester-csv")
    parser.add_argument("--symbol")
    parser.add_argument("--strategy")
    parser.add_argument("--rolling", action="store_true")
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--step-weeks", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--certification-mode", action="store_true", help="enforce locked-OOS provenance and temporal purity before evaluation")
    args = parser.parse_args()
    if args.tester_csv:
        rows = ingest_tester_csv(args.tester_csv)
        print(json.dumps({"rows": len(rows), "source": args.tester_csv}, indent=2))
        return
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
