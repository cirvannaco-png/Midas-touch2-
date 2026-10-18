from __future__ import annotations

import unittest

from tools.order_flow_research import (
    analyze,
    build_outcome_index,
    chronological_split,
    join_events_to_outcomes,
    load_order_flow_events,
    summarize,
)


def event(key: str, end: int, *, symbol: str = "EURUSD", timeframe: str = "PERIOD_M1",
          pressure: float = 0.4, bull: str = "true") -> dict[str, str]:
    return {
        "schema_version": "order-flow-evidence-v1", "event_key": key, "symbol": symbol, "timeframe": timeframe,
        "bar_end_epoch": str(end), "pressure_ratio": str(pressure),
        "bullish_sweep_reclaim": bull, "bearish_sweep_reclaim": "false",
        "absorption_proxy": "false", "exhaustion_proxy": "false",
        "data_quality": "1", "data_stale": "false",
    }


def signal(epoch: int, *, symbol: str = "EURUSD", timeframe: str = "PERIOD_M1",
           direction: str = "BUY") -> dict[str, str]:
    return {
        "SignalID": f"{symbol}_{direction}_{epoch}", "Symbol": symbol,
        "EntryTF": timeframe, "Direction": direction,
        "Session": "London", "Regime": "Trend", "VolRegime": "Normal",
        "SelectedStrategy": "Sweep",
    }


def outcome(epoch: int, resolved: int, realized_r: str = "1.0",
            *, filled: str = "Yes") -> dict[str, str]:
    return {
        "SignalID": f"EURUSD_BUY_{epoch}", "Filled": filled,
        "RealizedR": realized_r, "OutcomeEpoch": str(resolved),
    }


class OrderFlowResearchTests(unittest.TestCase):
    def test_join_uses_latest_prior_event(self) -> None:
        signals = [signal(1_700_000_105)]
        outcomes = [outcome(1_700_000_105, 1_700_000_500, "1.5")]
        index, rejected = build_outcome_index(signals, outcomes)
        normalized_events, event_rejected = load_order_flow_events(
            [event("old", 1_700_000_000, pressure=-0.3),
             event("new", 1_700_000_100, pressure=0.7)]
        )
        joined, join_rejected = join_events_to_outcomes(
            normalized_events, index, max_match_gap_seconds=120,
        )
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined[0]["event_key"], "new")
        self.assertEqual(joined[0]["pressure_ratio"], 0.7)
        self.assertEqual(joined[0]["realized_r"], 1.5)
        self.assertEqual(rejected, {})
        self.assertEqual(event_rejected, {})
        self.assertEqual(join_rejected, {})

    def test_future_event_is_never_joined(self) -> None:
        signals = [signal(1_700_000_100)]
        outcomes = [outcome(1_700_000_100, 1_700_000_500)]
        index, _ = build_outcome_index(signals, outcomes)
        normalized_events, _ = load_order_flow_events([event("future", 1_700_000_101)])
        joined, rejected = join_events_to_outcomes(normalized_events, index)
        self.assertEqual(joined, [])
        self.assertEqual(rejected["no_prior_same_symbol_timeframe_event"], 1)

    def test_stale_event_and_wrong_timeframe_are_rejected(self) -> None:
        signals = [signal(1_700_000_500)]
        outcomes = [outcome(1_700_000_500, 1_700_000_800)]
        index, _ = build_outcome_index(signals, outcomes)
        normalized_events, _ = load_order_flow_events(
            [event("stale", 1_700_000_000),
             event("wrong-tf", 1_700_000_490, timeframe="PERIOD_M5")]
        )
        joined, rejected = join_events_to_outcomes(
            normalized_events, index, max_match_gap_seconds=120,
        )
        self.assertEqual(joined, [])
        self.assertEqual(rejected["stale_event_for_signal"], 1)

    def test_unfilled_and_invalid_timing_outcomes_are_excluded(self) -> None:
        s1 = signal(1_700_000_100)
        s2 = signal(1_700_000_200, direction="SELL")
        rows = [
            {"SignalID": s1["SignalID"], "Filled": "No", "RealizedR": "0", "OutcomeEpoch": "1700000500"},
            {"SignalID": s2["SignalID"], "Filled": "Yes", "RealizedR": "2", "OutcomeEpoch": "1700000100"},
        ]
        index, rejected = build_outcome_index([s1, s2], rows)
        self.assertEqual(index, {})
        self.assertEqual(rejected["not_filled"], 1)
        self.assertEqual(rejected["outcome_precedes_decision"], 1)

    def test_default_join_window_uses_timeframe_length(self) -> None:
        s = signal(1_700_000_900, timeframe="PERIOD_M15")
        o = {"SignalID": s["SignalID"], "Filled": "Yes", "RealizedR": "1.0",
             "OutcomeEpoch": "1700001000"}
        index, _ = build_outcome_index([s], [o])
        events, _ = load_order_flow_events([
            event("m15-context", 1_700_000_001, timeframe="PERIOD_M15")
        ])
        joined, rejected = join_events_to_outcomes(events, index)
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined[0]["event_gap_seconds"], 899)
        self.assertEqual(rejected, {})

    def test_unknown_timeframe_fails_closed_without_manual_gap(self) -> None:
        s = signal(1_700_000_900, timeframe="PERIOD_MN1")
        o = {"SignalID": s["SignalID"], "Filled": "Yes", "RealizedR": "1.0",
             "OutcomeEpoch": "1700001000"}
        index, _ = build_outcome_index([s], [o])
        events, _ = load_order_flow_events([
            event("unknown-context", 1_700_000_850, timeframe="PERIOD_MN1")
        ])
        joined, rejected = join_events_to_outcomes(events, index)
        self.assertEqual(joined, [])
        self.assertEqual(rejected["unsupported_timeframe_for_default_match_window"], 1)

    def test_loader_rejects_stale_and_non_proxy_events(self) -> None:
        good = event("good", 1_700_000_000)
        stale = dict(event("stale", 1_700_000_001), data_stale="true")
        mislabeled = dict(event("bad-quality", 1_700_000_002), data_quality="2")
        events, rejected = load_order_flow_events([good, stale, mislabeled])
        self.assertEqual([r["event_key"] for r in events], ["good"])
        self.assertEqual(rejected["stale_event_record"], 1)
        self.assertEqual(rejected["unsupported_or_mislabeled_data_quality"], 1)

    def test_loader_rejects_unknown_schema_version(self) -> None:
        unknown = dict(event("future-schema", 1_700_000_003), schema_version="order-flow-evidence-v2")
        events, rejected = load_order_flow_events([unknown])
        self.assertEqual(events, [])
        self.assertEqual(rejected["unsupported_schema_version"], 1)

    def test_integrated_report_keeps_automatic_promotion_disabled(self) -> None:
        signals = [signal(1_700_000_100), signal(1_700_000_200), signal(1_700_000_300)]
        outcomes = [
            outcome(1_700_000_100, 1_700_000_150, "1.0"),
            outcome(1_700_000_200, 1_700_000_250, "-0.5"),
            outcome(1_700_000_300, 1_700_000_350, "0.2"),
        ]
        evidence = [
            event("e1", 1_700_000_095, pressure=0.4, bull="true"),
            event("e2", 1_700_000_195, pressure=-0.2, bull="false"),
            event("e3", 1_700_000_295, pressure=0.7, bull="true"),
        ]
        report = analyze(evidence, signals, outcomes, min_sample=1)
        self.assertEqual(report["matched_outcomes"], 3)
        self.assertEqual(report["matched_unique_event_count"], 3)
        self.assertEqual(report["signals_per_event"]["max_signals_per_event"], 1)
        self.assertEqual(report["chronological_holdout"]["train_count_after_purge"], 2)
        self.assertEqual(report["chronological_holdout"]["holdout_count"], 1)
        self.assertFalse(report["release_policy"]["automatic_promotion"])
        self.assertEqual(report["event_rejections"], {})
        self.assertEqual(report["feature_breakdown"]["direction=BUY"]["all_sample"]["n"], 3)
        self.assertEqual(report["feature_breakdown"]["regime=Trend"]["all_sample"]["n"], 3)

    def test_empty_source_rows_fail_with_readable_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "no data rows"):
            analyze([], [signal(1_700_000_100)], [outcome(1_700_000_100, 1_700_000_200)])

    def test_conflicting_duplicate_signal_is_fail_closed(self) -> None:
        s = signal(1_700_000_100)
        s2 = dict(s, Direction="SELL")
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            build_outcome_index([s, s2], [outcome(1_700_000_100, 1_700_000_500)])

    def test_metrics_are_in_realized_r_and_chronological(self) -> None:
        rows = [{"realized_r": x} for x in [1.0, -0.5, 0.0, -1.0, 2.0]]
        metrics = summarize(rows)
        self.assertEqual(metrics["n"], 5)
        self.assertEqual(metrics["wins"], 2)
        self.assertEqual(metrics["losses"], 2)
        self.assertEqual(metrics["scratches"], 1)
        self.assertAlmostEqual(metrics["expectancy_r"], 0.3)
        self.assertAlmostEqual(metrics["profit_factor"], 2.0)
        self.assertAlmostEqual(metrics["max_drawdown_r"], 1.5)

    def test_drawdown_uses_resolution_order_for_overlapping_positions(self) -> None:
        # Entry order is loss, win, loss; resolution order is win, loss, loss.
        rows = [
            {"decision_epoch": 100, "resolved_epoch": 400, "realized_r": -1.0},
            {"decision_epoch": 200, "resolved_epoch": 250, "realized_r": 2.0},
            {"decision_epoch": 300, "resolved_epoch": 350, "realized_r": -1.0},
        ]
        metrics = summarize(rows)
        self.assertAlmostEqual(metrics["max_drawdown_r"], 2.0)
        self.assertEqual(metrics["total_r"], 0.0)

    def test_chronological_split_purges_outcomes_overlapping_holdout(self) -> None:
        rows = []
        for i in range(10):
            decision = i * 100 + 1
            resolved = i * 100 + 50
            if i == 6:
                resolved = 750  # this training decision is resolved after test starts
            rows.append({
                "decision_epoch": decision,
                "resolved_epoch": resolved,
                "realized_r": 1.0,
            })
        split = chronological_split(rows, 0.30)
        self.assertEqual(split["test_start_epoch"], 701)
        self.assertEqual(len(split["test"]), 3)
        self.assertEqual(len(split["train"]), 6)
        self.assertEqual(split["purged_train"], 1)
        self.assertLess(max(r["resolved_epoch"] for r in split["train"]), split["test_start_epoch"])

    def test_empty_loss_side_does_not_claim_infinite_profit_factor(self) -> None:
        metrics = summarize([{"realized_r": 1.0}, {"realized_r": 2.0}])
        self.assertIsNone(metrics["profit_factor"])

if __name__ == "__main__":
    unittest.main()
