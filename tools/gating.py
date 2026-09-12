"""Statistically gated recalibration decisions.

Promotion/rollback is fail-closed: every gated metric must have enough
non-overlapping evidence in the required consecutive cycles. A single
improving metric cannot promote a candidate while another required metric is
still statistically indeterminate.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stats import Stat, direction, intervals_overlap  # noqa: E402

MIN_PERSISTENCE = 2
GATED_METRICS = ("win_rate", "confidence_auc", "confidence_r_correlation")


class GatingError(ValueError):
    pass


@dataclass
class MetricVerdict:
    metric: str
    prior: Stat
    latest: Stat
    overlap: bool | None
    moved: str | None


@dataclass
class Decision:
    action: str
    weight_version: str
    reasoning: list[str]
    metric_verdicts: list[MetricVerdict]
    cycles_considered: int

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "weight_version": self.weight_version,
            "reasoning": self.reasoning,
            "cycles_considered": self.cycles_considered,
            "metric_verdicts": [
                {"metric": v.metric, "prior": v.prior.to_dict(), "latest": v.latest.to_dict(),
                 "overlap": v.overlap, "moved": v.moved}
                for v in self.metric_verdicts
            ],
        }


def _extract_stat(cycle: dict, weight_version: str, metric: str) -> Stat:
    by_wv = cycle.get("expectancy", {}).get("by_weight_version_stats", {})
    block = by_wv.get(weight_version)
    if block is None:
        return Stat.empty(0)
    return Stat.from_dict(block.get(metric, {}))


def _validate_cycles(cycles: list[dict], weight_version: str) -> None:
    if not cycles:
        raise GatingError("empty cycle history — nothing to decide from")
    sources = {c.get("source") for c in cycles}
    if "synthetic" in sources and "live" in sources:
        raise GatingError("cycle history mixes synthetic and live cycles; filter explicitly to one source")
    for c in cycles:
        if c.get("source") not in {"live", "synthetic"} or not c.get("cycle_id"):
            raise GatingError("every cycle must carry source=live|synthetic and a non-empty cycle_id")


def decide(cycles: list[dict], weight_version: str, min_persistence: int = MIN_PERSISTENCE) -> Decision:
    _validate_cycles(cycles, weight_version)
    if min_persistence < 1:
        raise GatingError("min_persistence must be >= 1")
    if len(cycles) < min_persistence + 1:
        return Decision("INSUFFICIENT_DATA", weight_version,
                        [f"need at least {min_persistence + 1} cycles; received {len(cycles)}"], [], len(cycles))

    per_metric_directions: dict[str, list[str | None]] = {m: [] for m in GATED_METRICS}
    last_verdicts: list[MetricVerdict] = []
    reasoning: list[str] = []

    for i in range(1, len(cycles)):
        prior_cycle, latest_cycle = cycles[i - 1], cycles[i]
        for metric in GATED_METRICS:
            prior = _extract_stat(prior_cycle, weight_version, metric)
            latest = _extract_stat(latest_cycle, weight_version, metric)
            overlap = intervals_overlap(prior, latest)
            moved = direction(prior, latest) if overlap is False else None
            per_metric_directions[metric].append(moved)
            if i == len(cycles) - 1:
                last_verdicts.append(MetricVerdict(metric, prior, latest, overlap, moved))

    contradiction_found = False
    persistent_moves: dict[str, str] = {}
    incomplete: list[str] = []
    for metric in GATED_METRICS:
        recent = per_metric_directions[metric][-min_persistence:]
        if any(d is None for d in recent):
            incomplete.append(metric)
            reasoning.append(f"{metric}: insufficient persistent divergent evidence ({recent})")
            continue
        if len(set(recent)) > 1:
            contradiction_found = True
            reasoning.append(f"{metric}: CONTRADICTION — recent directions disagree ({recent})")
            continue
        persistent_moves[metric] = recent[0]
        reasoning.append(f"{metric}: persistent '{recent[0]}' across {min_persistence} cycles")

    if contradiction_found:
        action = "ROLLBACK"
        reasoning.insert(0, "Active statistical contradiction detected — fail safe to the last known-good configuration.")
    elif incomplete:
        action = "HOLD"
        reasoning.insert(0, "Required gated metrics are not all statistically resolved — no promotion or rollback is permitted.")
    elif all(persistent_moves[m] == "down" for m in GATED_METRICS):
        action = "ROLLBACK"
        reasoning.insert(0, "Every required gated metric persistently regressed — rollback eligible.")
    elif all(persistent_moves[m] == "up" for m in GATED_METRICS):
        action = "PROMOTE"
        reasoning.insert(0, "Every required gated metric persistently improved with no contradiction — promotion eligible, subject to the human approval gate.")
    else:
        action = "HOLD"
        reasoning.insert(0, "Required metrics do not agree on one persistent direction — hold.")

    return Decision(action, weight_version, reasoning, last_verdicts, len(cycles))


def load_cycles_from_dir(path: str, weight_version: str | None, source: str | None) -> list[dict]:
    files = sorted(f for f in os.listdir(path) if f.endswith(".json"))
    cycles = []
    for fname in files:
        with open(os.path.join(path, fname), encoding="utf-8") as fh:
            c = json.load(fh)
        if weight_version and weight_version not in c.get("expectancy", {}).get("by_weight_version_stats", {}):
            continue
        if source and c.get("source") != source:
            continue
        cycles.append(c)
    cycles.sort(key=lambda c: c.get("generated_at", ""))
    return cycles


async def load_cycles_from_db(weight_version: str | None, source: str | None) -> list[dict]:
    from _pathutil import ensure_bridge_importable
    ensure_bridge_importable(__file__)
    from sqlalchemy import select
    from app.database import async_session
    from app.models import CalibrationCycle

    async with async_session() as session:
        stmt = select(CalibrationCycle).order_by(CalibrationCycle.generated_at.asc())
        if source:
            stmt = stmt.where(CalibrationCycle.source == source)
        rows = (await session.execute(stmt)).scalars().all()
    cycles = []
    for row in rows:
        c = dict(row.report_json)
        c["source"] = row.source
        c["cycle_id"] = row.cycle_id
        c.setdefault("generated_at", row.generated_at.isoformat() if row.generated_at else None)
        if weight_version and weight_version not in c.get("expectancy", {}).get("by_weight_version_stats", {}):
            continue
        cycles.append(c)
    return cycles


def print_decision(d: Decision) -> None:
    print("=" * 72)
    print(f"GATING DECISION — {d.weight_version}")
    print("=" * 72)
    print(f"Action:              {d.action}")
    print(f"Cycles considered:   {d.cycles_considered}")
    print("\nReasoning:")
    for line in d.reasoning:
        print(f"  - {line}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--history")
    parser.add_argument("--db", action="store_true")
    parser.add_argument("--weight-version", required=True)
    parser.add_argument("--source", choices=["live", "synthetic"])
    parser.add_argument("--min-persistence", type=int, default=MIN_PERSISTENCE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.db == bool(args.history):
        print("gating: pass exactly one of --history <dir> or --db", file=sys.stderr)
        sys.exit(2)
    if args.db:
        import asyncio
        cycles = asyncio.run(load_cycles_from_db(args.weight_version, args.source))
    else:
        cycles = load_cycles_from_dir(args.history, args.weight_version, args.source)
    try:
        decision = decide(cycles, args.weight_version, args.min_persistence)
    except GatingError as e:
        print(f"gating: {e}", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2, default=str))
    else:
        print_decision(decision)


if __name__ == "__main__":
    main()
