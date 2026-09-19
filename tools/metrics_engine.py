"""
tools/metrics_engine.py — Step 2 of the trade-tagging system: the
two-track metrics engine.

Queries `signal_outcomes` and reports coverage and expectancy as separate
tracks. Coverage counts every signal; expectancy counts resolved outcomes.
The engine never treats a missing realized-R value as zero.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
from _pathutil import ensure_bridge_importable  # noqa: E402
ensure_bridge_importable(__file__)

try:
    from sqlalchemy import select
    from app.database import async_session
    from app.models import SignalOutcome
except ImportError as exc:  # pragma: no cover
    print(
        "metrics_engine: couldn't import the bridge's `app` package "
        f"({exc}). Run this from telegram-bridge/, or with telegram-bridge/ "
        "on PYTHONPATH — it deliberately reuses the bridge's own DB "
        "connection/settings rather than duplicating them.",
        file=sys.stderr,
    )
    sys.exit(1)

from stats import auc_with_ci, pearson_ci, wilson_ci
from instrument_taxonomy import classify_symbol

RESOLVED_OUTCOMES = {"win", "loss", "scratch"}
CONFIDENCE_BUCKET_WIDTH = 10.0


@dataclass
class TagBreakdown:
    tag_value: str
    total: int = 0
    by_outcome: dict = field(default_factory=lambda: defaultdict(int))
    by_direction: dict = field(default_factory=lambda: defaultdict(int))
    realized_r_sum: float = 0.0
    realized_r_count: int = 0
    commission_cost_sum: float = 0.0
    spread_cost_sum: float = 0.0
    slippage_cost_sum: float = 0.0
    cost_count: int = 0

    @property
    def resolved_count(self) -> int:
        return sum(self.by_outcome.get(o, 0) for o in RESOLVED_OUTCOMES)

    @property
    def win_rate(self) -> float | None:
        if self.resolved_count == 0:
            return None
        return self.by_outcome.get("win", 0) / self.resolved_count

    @property
    def avg_r(self) -> float | None:
        if self.realized_r_count == 0:
            return None
        return self.realized_r_sum / self.realized_r_count

    @property
    def no_fill_rate(self) -> float | None:
        if self.total == 0:
            return None
        return self.by_outcome.get("no_fill", 0) / self.total


def _group_by(rows, keyfn):
    out: dict[str, list] = defaultdict(list)
    for r in rows:
        out[keyfn(r) or "(untagged)"].append(r)
    return dict(out)


def _bucket(rows, keyfn):
    out: dict[str, TagBreakdown] = {}
    for r in rows:
        key = keyfn(r) or "(untagged)"
        tb = out.setdefault(key, TagBreakdown(tag_value=key))
        tb.total += 1
        tb.by_outcome[r.outcome] += 1
        tb.by_direction[r.direction] += 1
        if r.outcome in RESOLVED_OUTCOMES and r.realized_r is not None:
            tb.realized_r_sum += r.realized_r
            tb.realized_r_count += 1
        if getattr(r, "filled", False) and all(v is not None for v in (getattr(r, "commission_cost", None), getattr(r, "spread_cost", None), getattr(r, "slippage_cost", None))):
            tb.commission_cost_sum += r.commission_cost
            tb.spread_cost_sum += r.spread_cost
            tb.slippage_cost_sum += r.slippage_cost
            tb.cost_count += 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1].total))


def _resolved_stats(rows) -> dict:
    resolved = [r for r in rows if r.outcome in RESOLVED_OUTCOMES]
    win_scores = [r.confidence_at_signal for r in resolved if r.outcome == "win" and r.confidence_at_signal is not None]
    loss_scores = [r.confidence_at_signal for r in resolved if r.outcome == "loss" and r.confidence_at_signal is not None]
    pairs = [
        (r.confidence_at_signal, r.realized_r)
        for r in resolved
        if r.confidence_at_signal is not None and r.realized_r is not None
    ]
    wins = sum(1 for r in resolved if r.outcome == "win")
    return {
        "win_rate": wilson_ci(wins, len(resolved)).to_dict(),
        "confidence_auc": auc_with_ci(win_scores, loss_scores).to_dict(),
        "confidence_r_correlation": pearson_ci(pairs).to_dict(),
    }


def compute_report(rows) -> dict:
    total = len(rows)
    resolved = [r for r in rows if r.outcome in RESOLVED_OUTCOMES]
    no_fill = [r for r in rows if r.outcome == "no_fill"]
    ambiguous = [r for r in rows if r.outcome == "ambiguous"]

    by_direction_total = defaultdict(int)
    by_direction_no_fill = defaultdict(int)
    for r in rows:
        by_direction_total[r.direction] += 1
        if r.outcome == "no_fill":
            by_direction_no_fill[r.direction] += 1

    realized_r_values = [r.realized_r for r in resolved if r.realized_r is not None]
    coverage = {
        "total_signals": total,
        "no_fill_count": len(no_fill),
        "no_fill_rate": (len(no_fill) / total) if total else None,
        "ambiguous_count": len(ambiguous),
        "directional_bias": {
            d: {
                "count": by_direction_total[d],
                "share": by_direction_total[d] / total if total else None,
                "no_fill_rate": by_direction_no_fill[d] / by_direction_total[d] if by_direction_total[d] else None,
            }
            for d in by_direction_total
        },
        "by_regime": {k: _tb_to_coverage_dict(v) for k, v in _bucket(rows, lambda r: r.regime).items()},
        "by_session": {k: _tb_to_coverage_dict(v) for k, v in _bucket(rows, lambda r: r.session).items()},
        "by_weight_version": {k: _tb_to_coverage_dict(v) for k, v in _bucket(rows, lambda r: r.weight_version).items()},
        "by_symbol": {k: _tb_to_coverage_dict(v) for k, v in _bucket(rows, lambda r: r.symbol).items()},
        "by_asset_class": {k: _tb_to_coverage_dict(v) for k, v in _bucket(rows, lambda r: classify_symbol(r.symbol)).items()},
        "by_strategy": {k: _tb_to_coverage_dict(v) for k, v in _bucket(rows, lambda r: r.strategy).items()},
    }

    expectancy = {
        "resolved_count": len(resolved),
        "overall_win_rate": sum(1 for r in resolved if r.outcome == "win") / len(resolved) if resolved else None,
        # Missing realized-R values are excluded from the denominator rather
        # than silently becoming zero. This keeps expectancy mathematically
        # aligned with the per-tag avg_r implementation below.
        "overall_avg_r": sum(realized_r_values) / len(realized_r_values) if realized_r_values else None,
        "overall_stats": _resolved_stats(rows),
        "by_weight_version_stats": {
            wv: _resolved_stats(group_rows)
            for wv, group_rows in _group_by(rows, lambda r: r.weight_version).items()
        },
        "by_regime": {k: _tb_to_expectancy_dict(v) for k, v in _bucket(rows, lambda r: r.regime).items()},
        "by_session": {k: _tb_to_expectancy_dict(v) for k, v in _bucket(rows, lambda r: r.session).items()},
        "by_sweep_grade": {k: _tb_to_expectancy_dict(v) for k, v in _bucket(rows, lambda r: r.sweep_grade).items()},
        "by_htf_ob_aligned": {
            k: _tb_to_expectancy_dict(v)
            for k, v in _bucket(rows, lambda r: "aligned" if r.htf_ob_aligned else "not_aligned").items()
        },
        "by_weight_version": {k: _tb_to_expectancy_dict(v) for k, v in _bucket(rows, lambda r: r.weight_version).items()},
        "by_symbol": {k: _tb_to_expectancy_dict(v) for k, v in _bucket(rows, lambda r: r.symbol).items()},
        "by_asset_class": {k: _tb_to_expectancy_dict(v) for k, v in _bucket(rows, lambda r: classify_symbol(r.symbol)).items()},
        "by_strategy": {k: _tb_to_expectancy_dict(v) for k, v in _bucket(rows, lambda r: r.strategy).items()},
        "by_strategy_stats": {k: _resolved_stats(group_rows) for k, group_rows in _group_by(rows, lambda r: r.strategy).items()},
        "by_resolution": {k: _tb_to_expectancy_dict(v) for k, v in _bucket(rows, lambda r: r.resolution).items()},
        "realized_r_by_confidence_decile": _confidence_deciles(resolved),
    }
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "coverage": coverage, "expectancy": expectancy}


def _tb_to_coverage_dict(tb: TagBreakdown) -> dict:
    return {"total": tb.total, "no_fill_rate": tb.no_fill_rate, "buy_count": tb.by_direction.get("BUY", 0), "sell_count": tb.by_direction.get("SELL", 0)}


def _tb_to_expectancy_dict(tb: TagBreakdown) -> dict:
    return {
        "resolved_count": tb.resolved_count,
        "win_rate": tb.win_rate,
        "avg_r": tb.avg_r,
        "cost_observations": tb.cost_count,
        "commission_cost_total": tb.commission_cost_sum if tb.cost_count else None,
        "spread_cost_total": tb.spread_cost_sum if tb.cost_count else None,
        "slippage_cost_total": tb.slippage_cost_sum if tb.cost_count else None,
    }


def _confidence_deciles(resolved_rows) -> dict:
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in resolved_rows:
        if r.confidence_at_signal is None or r.realized_r is None:
            continue
        lo = int(r.confidence_at_signal // CONFIDENCE_BUCKET_WIDTH) * int(CONFIDENCE_BUCKET_WIDTH)
        hi = lo + int(CONFIDENCE_BUCKET_WIDTH)
        buckets[f"{lo}-{hi}"].append(r.realized_r)
    return {k: {"n": len(v), "avg_r": sum(v) / len(v)} for k, v in sorted(buckets.items(), key=lambda kv: int(kv[0].split("-")[0]))}


def compute_regime_matrix(rows) -> list[dict]:
    buckets: dict[tuple, list] = defaultdict(list)
    for r in rows:
        if r.outcome not in RESOLVED_OUTCOMES:
            continue
        key = (r.symbol, r.strategy or "(untagged)", r.session or "(untagged)", r.regime or "(untagged)")
        buckets[key].append(r)

    out = []
    for (symbol, strategy, session_tag, regime), bucket_rows in buckets.items():
        bucket_rows.sort(key=lambda r: (getattr(r, "signal_time", None) or r.received_at or datetime.min.replace(tzinfo=timezone.utc)))
        n = len(bucket_rows)
        wins = sum(1 for r in bucket_rows if r.outcome == "win")
        r_values = [r.realized_r for r in bucket_rows if r.realized_r is not None]
        gains = sum(v for v in r_values if v > 0)
        losses_abs = abs(sum(v for v in r_values if v < 0))
        pf = (gains / losses_abs) if losses_abs > 0 else None
        cum, peak, max_dd = 0.0, 0.0, 0.0
        for v in r_values:
            cum += v
            peak = max(peak, cum)
            max_dd = max(max_dd, peak - cum)
        out.append({
            "symbol": symbol, "strategy": strategy, "asset_class": classify_symbol(symbol),
            "session": session_tag, "regime": regime, "trades": n,
            "win_rate": (wins / n) if n else None,
            "avg_r": (sum(r_values) / len(r_values)) if r_values else None,
            "profit_factor": pf, "max_drawdown_r": max_dd,
        })
    out.sort(key=lambda d: -d["trades"])
    return out


def print_regime_matrix(matrix: list[dict]) -> None:
    print("=" * 96)
    print("REGIME MATRIX — Symbol x Session x Volatility (resolved trades only)")
    print("=" * 96)
    header = f"{'Symbol':10s} {'Strategy':18s} {'Asset':10s} {'Session':10s} {'Regime':12s} {'Trades':>7s} {'Win %':>8s} {'Avg R':>8s} {'PF':>6s} {'MaxDD(R)':>9s}"
    print(header)
    print("-" * len(header))
    for row in matrix:
        win_pct = f"{row['win_rate'] * 100:.1f}%" if row["win_rate"] is not None else "n/a"
        avg_r = f"{row['avg_r']:+.2f}" if row["avg_r"] is not None else "n/a"
        pf = f"{row['profit_factor']:.2f}" if row["profit_factor"] is not None else "n/a"
        print(f"{row['symbol']:10s} {row['strategy']:18s} {row['asset_class']:10s} {row['session']:10s} {row['regime']:12s} {row['trades']:7d} {win_pct:>8s} {avg_r:>8s} {pf:>6s} {row['max_drawdown_r']:9.2f}")
    print()


def _fmt_pct(x):
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _fmt_r(x):
    return f"{x:+.2f}R" if x is not None else "n/a"


def _fmt_ci(stat_dict: dict, pct: bool = False) -> str:
    v, lo, hi, n = stat_dict.get("value"), stat_dict.get("ci_low"), stat_dict.get("ci_high"), stat_dict.get("n", 0)
    if v is None:
        return f"n/a (n={n}, not enough data)"
    if pct:
        return f"{v * 100:.1f}% [{lo * 100:.1f}%, {hi * 100:.1f}%]  (n={n})"
    return f"{v:.3f} [{lo:.3f}, {hi:.3f}]  (n={n})"


def print_report(report: dict) -> None:
    cov, exp = report["coverage"], report["expectancy"]
    print("=" * 72)
    print(f"TWO-TRACK METRICS REPORT — {report['generated_at']}")
    print("=" * 72)
    print("\n--- COVERAGE (every signal, including no-fill/ambiguous) ---")
    print(f"Total signals:      {cov['total_signals']}")
    print(f"No-fill rate:       {_fmt_pct(cov['no_fill_rate'])} ({cov['no_fill_count']} signals)")
    print(f"Ambiguous count:    {cov['ambiguous_count']}")
    print("\nDirectional bias:")
    for d, v in cov["directional_bias"].items():
        print(f"  {d:5s} count={v['count']:5d}  share={_fmt_pct(v['share'])}  no_fill_rate={_fmt_pct(v['no_fill_rate'])}")
    print("\nSignal frequency by regime:")
    for k, v in cov["by_regime"].items():
        print(f"  {k:14s} total={v['total']:5d}  no_fill_rate={_fmt_pct(v['no_fill_rate'])}  buy={v['buy_count']} sell={v['sell_count']}")
    print("\nSignal frequency by session:")
    for k, v in cov["by_session"].items():
        print(f"  {k:14s} total={v['total']:5d}  no_fill_rate={_fmt_pct(v['no_fill_rate'])}  buy={v['buy_count']} sell={v['sell_count']}")
    print("\nSignal frequency by weight version:")
    for k, v in cov["by_weight_version"].items():
        print(f"  {k:20s} total={v['total']:5d}  no_fill_rate={_fmt_pct(v['no_fill_rate'])}")
    print("\n--- EXPECTANCY (resolved trades only: win/loss/scratch) ---")
    print(f"Resolved count:     {exp['resolved_count']}")
    print(f"Overall win rate:   {_fmt_pct(exp['overall_win_rate'])}")
    print(f"Overall avg R:      {_fmt_r(exp['overall_avg_r'])}")
    st = exp["overall_stats"]
    print("\nOverall statistics (CIs, not point estimates):")
    print(f"  win_rate:              {_fmt_ci(st['win_rate'], pct=True)}")
    print(f"  confidence AUC:        {_fmt_ci(st['confidence_auc'])}")
    print(f"  confidence-R corr.:    {_fmt_ci(st['confidence_r_correlation'])}")
    print("\nBy weight version (CIs):")
    for wv, s in exp["by_weight_version_stats"].items():
        print(f"  {wv}")
        print(f"    win_rate:            {_fmt_ci(s['win_rate'], pct=True)}")
        print(f"    confidence AUC:      {_fmt_ci(s['confidence_auc'])}")
        print(f"    confidence-R corr.:  {_fmt_ci(s['confidence_r_correlation'])}")
    print("\nBy regime:")
    for k, v in exp["by_regime"].items():
        print(f"  {k:14s} n={v['resolved_count']:5d}  win_rate={_fmt_pct(v['win_rate'])}  avg_r={_fmt_r(v['avg_r'])}")
    print("\nBy session:")
    for k, v in exp["by_session"].items():
        print(f"  {k:14s} n={v['resolved_count']:5d}  win_rate={_fmt_pct(v['win_rate'])}  avg_r={_fmt_r(v['avg_r'])}")
    print("\nBy sweep grade:")
    for k, v in exp["by_sweep_grade"].items():
        print(f"  {k:14s} n={v['resolved_count']:5d}  win_rate={_fmt_pct(v['win_rate'])}  avg_r={_fmt_r(v['avg_r'])}")
    print("\nBy HTF OB alignment:")
    for k, v in exp["by_htf_ob_aligned"].items():
        print(f"  {k:14s} n={v['resolved_count']:5d}  win_rate={_fmt_pct(v['win_rate'])}  avg_r={_fmt_r(v['avg_r'])}")
    print("\nBy weight version:")
    for k, v in exp["by_weight_version"].items():
        print(f"  {k:20s} n={v['resolved_count']:5d}  win_rate={_fmt_pct(v['win_rate'])}  avg_r={_fmt_r(v['avg_r'])}")
    print("\nRealized R by confidence decile (resolved trades only):")
    for k, v in exp["realized_r_by_confidence_decile"].items():
        print(f"  confidence {k:8s} n={v['n']:5d}  avg_r={_fmt_r(v['avg_r'])}")
    print()


async def fetch_rows(since: datetime | None, weight_version: str | None):
    async with async_session() as session:
        stmt = select(SignalOutcome)
        if since is not None:
            stmt = stmt.where(SignalOutcome.received_at >= since)
        if weight_version is not None:
            stmt = stmt.where(SignalOutcome.weight_version == weight_version)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def run(args) -> int:
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since else None
    rows = await fetch_rows(since, args.weight_version)
    if not rows:
        print("metrics_engine: no rows in signal_outcomes matching the given filters.", file=sys.stderr)
        return 1
    report = compute_report(rows)
    if args.regime_matrix:
        matrix = compute_regime_matrix(rows)
        if args.json:
            print(json.dumps(matrix, indent=2, default=str))
        else:
            print_regime_matrix(matrix)
        return 0
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", help="ISO date/datetime — only rows received at/after this (e.g. 2026-08-01)")
    parser.add_argument("--weight-version", help="only rows tagged with this exact weight_version")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--regime-matrix", action="store_true", help="print the Symbol x Session x Volatility matrix")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
