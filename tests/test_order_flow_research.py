from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from tools.order_flow_research import (
    analyze,
    build_attribution_index,
    build_outcome_index,
    chronological_split,
    join_events_to_outcomes,
    load_order_flow_events,
    read_csv,
    summarize,
    _annotate_order_flow_proxies,
)


def event(key: str, end: int, *, symbol: str = "EURUSD", timeframe: str = "PERIOD_M1",
          pressure: float = 0.4, bull: str = "true") -> dict[str, str]:
    return {
        "schema_version": "order-flow-evidence-v2", "event_key": key, "symbol": symbol, "timeframe": timeframe,
        "bar_end_epoch": str(end), "pressure_ratio": str(pressure),
        "bullish_sweep_reclaim": bull, "bearish_sweep_reclaim": "false",
        "absorption_proxy": "false", "exhaustion_proxy": "false",
        "data_quality": "1", "data_stale": "false", "diagnostic_status": "OK_PROXY",
    }


def signal(epoch: int, *, symbol: str = "EURUSD", timeframe: str = "PERIOD_M1",
           direction: str = "BUY") -> dict[str, str]:
    return {
        "SignalID": f"{symbol}_{direction}_{epoch}", "Symbol": symbol,
        "EntryTF": timeframe, "Direction": direction,
        "Session": "London", "Regime": "Trend", "VolRegime": "Normal",
        "SelectedStrategy": "Sweep",
    }


def attribution(signal_row: dict[str, str], event_key: str, *, status: str = "MATCHED") -> dict[str, str]:
    return {
        "schema_version": "order-flow-attribution-v1",
        "signal_id": signal_row["SignalID"],
        "event_key": event_key,
        "symbol": signal_row["Symbol"],
        "timeframe": signal_row["EntryTF"],
        "direction": signal_row["Direction"],
        "signal_epoch": signal_row["SignalID"].rsplit("_", 1)[-1],
        "attribution_status": status,
    }


def attribution_v2(signal_row: dict[str, str], event_key: str, *,
                   status: str = "MATCHED", decision_id: str = "42",
                   fingerprint: str = "sha256:test-fingerprint") -> dict[str, str]:
    row = attribution(signal_row, event_key, status=status)
    row.update({
        "schema_version": "order-flow-attribution-v2",
        "decision_id": decision_id,
        "decision_fingerprint": fingerprint,
    })
    return row


def attribution_v3(signal_row: dict[str, str], event_key: str, *,
                   status: str = "MATCHED", decision_id: str = "42",
                   fingerprint: str = "sha256:test-fingerprint") -> dict[str, str]:
    row = attribution_v2(signal_row, event_key, status=status,
                         decision_id=decision_id, fingerprint=fingerprint)
    row.update({
        "schema_version": "order-flow-attribution-v3",
        "smc_inducement_valid": "true",
        "smc_liquidity_swept": "true",
        "smc_bos_confirmed": "false",
        "smc_sweep_grade": "SWEEP_GRADE_A",
        "smc_bos_strength": "0.85",
        "smc_time_decay": "0.75",
    })
    return row


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

    def test_direct_attribution_uses_exact_event_not_nearest_time(self) -> None:
        s = signal(1_700_000_105)
        o = outcome(1_700_000_105, 1_700_000_500, "1.25")
        evidence, _ = load_order_flow_events([
            event("exact-event", 1_700_000_100, pressure=-0.4),
            event("closer-but-not-linked", 1_700_000_104, pressure=0.8),
        ])
        outcome_index, _ = build_outcome_index([s], [o])
        attr_index, attr_rejected = build_attribution_index([attribution(s, "exact-event")])
        joined, rejected = join_events_to_outcomes(
            evidence, outcome_index, attribution_index=attr_index
        )
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined[0]["event_key"], "exact-event")
        self.assertEqual(joined[0]["pressure_ratio"], -0.4)
        self.assertEqual(attr_rejected, {})
        self.assertEqual(rejected, {})

    def test_v2_attribution_preserves_decision_lineage_in_joined_rows(self) -> None:
        s = signal(1_700_000_105)
        o = outcome(1_700_000_105, 1_700_000_500, "1.25")
        evidence, _ = load_order_flow_events([event("exact-v2", 1_700_000_100)])
        outcome_index, _ = build_outcome_index([s], [o])
        attr_index, attr_rejected = build_attribution_index([
            attribution_v2(s, "exact-v2", decision_id="987654")
        ])
        joined, rejected = join_events_to_outcomes(
            evidence, outcome_index, attribution_index=attr_index
        )
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined[0]["decision_id"], "987654")
        self.assertEqual(joined[0]["decision_fingerprint"], "sha256:test-fingerprint")
        self.assertEqual(joined[0]["event_key"], "exact-v2")
        self.assertEqual(attr_rejected, {})
        self.assertEqual(rejected, {})

    def test_v3_attribution_preserves_smc_context_for_stratified_research(self) -> None:
        s = signal(1_700_000_105)
        o = outcome(1_700_000_105, 1_700_000_500, "1.25")
        evidence = [event("exact-v3", 1_700_000_100)]
        report = analyze(evidence, [s], [o],
                         attribution_rows=[attribution_v3(s, "exact-v3")],
                         min_sample=1)
        self.assertEqual(report["matched_outcomes"], 1)
        self.assertEqual(report["attribution_rejections"], {})
        self.assertIn("smc_inducement_valid=true", report["feature_breakdown"])
        self.assertIn("smc_sweep_grade=SWEEP_GRADE_A", report["feature_breakdown"])
        self.assertEqual(report["feature_breakdown"]["smc_inducement_valid=true"]["all_sample"]["n"], 1)

    def test_v3_attribution_rejects_invalid_smc_context(self) -> None:
        s = signal(1_700_000_105)
        row = attribution_v3(s, "exact-v3")
        row["smc_sweep_grade"] = "INSTITUTIONAL_CONFIRMED"
        indexed, rejected = build_attribution_index([row])
        self.assertEqual(indexed, {})
        self.assertEqual(rejected["invalid_smc_context"], 1)

    def test_v2_attribution_without_decision_lineage_is_rejected(self) -> None:
        s = signal(1_700_000_105)
        row = attribution_v2(s, "exact-v2")
        row.pop("decision_fingerprint")
        indexed, rejected = build_attribution_index([row])
        self.assertEqual(indexed, {})
        self.assertEqual(rejected["missing_decision_lineage"], 1)

    def test_direct_mode_never_falls_back_when_attribution_missing(self) -> None:
        s = signal(1_700_000_105)
        o = outcome(1_700_000_105, 1_700_000_500, "1.0")
        evidence, _ = load_order_flow_events([event("nearest", 1_700_000_100)])
        outcome_index, _ = build_outcome_index([s], [o])
        joined, rejected = join_events_to_outcomes(
            evidence, outcome_index, attribution_index={}
        )
        self.assertEqual(joined, [])
        self.assertEqual(rejected["missing_direct_attribution"], 1)

    def test_no_usable_event_attribution_is_rejected_explicitly(self) -> None:
        s = signal(1_700_000_105)
        rows = [attribution(s, "", status="NO_USABLE_EVENT")]
        indexed, rejected = build_attribution_index(rows)
        self.assertEqual(indexed, {})
        self.assertEqual(rejected["status_no_usable_event"], 1)

    def test_analyzer_reports_direct_attribution_mode_and_status_rejections(self) -> None:
        s = signal(1_700_000_105)
        o = outcome(1_700_000_105, 1_700_000_500, "1.0")
        evidence = [event("linked", 1_700_000_100)]
        attr = [attribution(s, "", status="NO_EVENT_KEY")]
        report = analyze(evidence, [s], [o], attribution_rows=attr, min_sample=1)
        self.assertEqual(report["attribution_mode"], "direct_signal_id")
        self.assertEqual(report["matched_outcomes"], 0)
        self.assertEqual(report["attribution_rejections"]["status_no_event_key"], 1)
        self.assertEqual(report["join_rejections"]["missing_direct_attribution"], 1)

    def test_direct_attribution_rejects_future_feature_event(self) -> None:
        s = signal(1_700_000_105)
        o = outcome(1_700_000_105, 1_700_000_500, "1.0")
        evidence = [event("future-direct", 1_700_000_106)]
        report = analyze(evidence, [s], [o],
                         attribution_rows=[attribution(s, "future-direct")],
                         min_sample=1)
        self.assertEqual(report["matched_outcomes"], 0)
        self.assertEqual(report["join_rejections"]["direct_attribution_event_after_signal"], 1)

    def test_direct_attribution_rejects_identity_mismatch(self) -> None:
        s = signal(1_700_000_105)
        o = outcome(1_700_000_105, 1_700_000_500, "1.0")
        evidence = [event("linked", 1_700_000_100)]
        attr = attribution(s, "linked")
        attr["timeframe"] = "PERIOD_M5"
        report = analyze(evidence, [s], [o], attribution_rows=[attr], min_sample=1)
        self.assertEqual(report["matched_outcomes"], 0)
        self.assertEqual(report["join_rejections"]["attribution_identity_mismatch"], 1)

    def test_loader_rejects_stale_and_non_proxy_events(self) -> None:
        good = event("good", 1_700_000_000)
        stale = dict(event("stale", 1_700_000_001), data_stale="true")
        mislabeled = dict(event("bad-quality", 1_700_000_002), data_quality="2")
        events, rejected = load_order_flow_events([good, stale, mislabeled])
        self.assertEqual([r["event_key"] for r in events], ["good"])
        self.assertEqual(rejected["stale_event_record"], 1)
        self.assertEqual(rejected["unsupported_or_mislabeled_data_quality"], 1)

    def test_loader_accounts_for_missing_tick_windows_without_using_them(self) -> None:
        missing = dict(
            event("missing", 1_700_000_010),
            data_quality="0", data_stale="true", diagnostic_status="NO_TICKS",
        )
        usable = event("usable", 1_700_000_000)
        events, rejected = load_order_flow_events([missing, usable])
        self.assertEqual([row["event_key"] for row in events], ["usable"])
        self.assertEqual(rejected["status_no_ticks"], 1)

    def test_loader_rejects_unknown_schema_version(self) -> None:
        unknown = dict(event("future-schema", 1_700_000_003), schema_version="order-flow-evidence-v999")
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
        self.assertEqual(report["source_evidence_row_count"], 3)
        self.assertEqual(report["distinct_evidence_event_keys"], 3)
        self.assertEqual(report["usable_evidence_fraction"], 1.0)
        self.assertEqual(report["matched_unique_event_count"], 3)
        self.assertEqual(report["signals_per_event"]["max_signals_per_event"], 1)
        self.assertEqual(report["chronological_holdout"]["train_count_after_purge"], 2)
        self.assertEqual(report["chronological_holdout"]["holdout_count"], 1)
        self.assertFalse(report["release_policy"]["automatic_promotion"])
        self.assertEqual(report["event_rejections"], {})
        self.assertEqual(report["feature_breakdown"]["direction=BUY"]["all_sample"]["n"], 3)
        self.assertEqual(report["feature_breakdown"]["regime=Trend"]["all_sample"]["n"], 3)

    def test_read_csv_supports_utf8_bom_and_comma_delimiter(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "signals.csv"
            path.write_text("\ufeffSignalID,RealizedR\nsig-1,1.25\n", encoding="utf-8")
            rows = read_csv(path)
        self.assertEqual(rows, [{"SignalID": "sig-1", "RealizedR": "1.25"}])

    def test_read_csv_supports_semicolon_delimiter(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "outcomes.csv"
            path.write_text("SignalID;RealizedR\nsig-1;1.25\nsig-2;-0.5\n", encoding="utf-8")
            rows = read_csv(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["RealizedR"], "-0.5")

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


class OrderFlowProxyAnnotationTests(unittest.TestCase):
    @staticmethod
    def proxy_event(key: str, end: int, *, signed: float, up: int, down: int,
                    close: float, atr: float, location: int, continuation: int) -> dict:
        return {
            "event_key": key, "symbol": "EURUSD", "timeframe": "PERIOD_M1",
            "bar_end_epoch": end, "schema_version": "order-flow-evidence-v3",
            "pressure_ratio": (up - down) / max(1, up + down),
            "signed_tick_pressure": signed, "positive_tick_count": up, "negative_tick_count": down,
            "bar_close": close, "atr": atr, "price_progress": 0.5 if signed >= 0 else -0.5,
            "prior_high": close + 1.0, "prior_low": close - 1.0,
            "pressure_progress_divergence": False, "auction_context_available": True,
            "auction_location": location, "continuation_hypothesis": continuation,
            "reversal_hypothesis": 0,
        }

    def test_cumulative_pressure_is_chronological_and_resets_at_utc_day(self) -> None:
        start = 1_700_000_100
        first = self.proxy_event("e1", start, signed=4, up=5, down=1, close=100, atr=1, location=2, continuation=1)
        second = self.proxy_event("e2", start + 60, signed=2, up=4, down=2, close=98, atr=1, location=-2, continuation=-1)
        next_day = self.proxy_event("e3", start + 86400, signed=-3, up=1, down=4, close=99, atr=1, location=0, continuation=0)

        rows = _annotate_order_flow_proxies([next_day, second, first])
        by_key = {row["event_key"]: row for row in rows}
        self.assertEqual(by_key["e1"]["utc_day_cumulative_tick_pressure_proxy"], 4.0)
        self.assertEqual(by_key["e2"]["utc_day_cumulative_tick_pressure_proxy"], 6.0)
        self.assertAlmostEqual(by_key["e2"]["utc_day_cumulative_pressure_ratio_proxy"], 0.5)
        self.assertEqual(by_key["e3"]["utc_day_cumulative_tick_pressure_proxy"], -3.0)
        self.assertAlmostEqual(by_key["e3"]["utc_day_cumulative_pressure_ratio_proxy"], -0.6)

    def test_price_pressure_divergence_and_auction_tags_are_descriptive(self) -> None:
        start = 1_700_000_100
        first = self.proxy_event("e1", start, signed=4, up=5, down=1, close=100, atr=1, location=2, continuation=1)
        second = self.proxy_event("e2", start + 60, signed=2, up=4, down=2, close=98, atr=1, location=2, continuation=1)

        rows = _annotate_order_flow_proxies([first, second])
        by_key = {row["event_key"]: row for row in rows}
        self.assertFalse(by_key["e1"]["utc_day_pressure_price_divergence"])
        self.assertTrue(by_key["e2"]["utc_day_pressure_price_divergence"])
        self.assertEqual(by_key["e2"]["auction_location_label"], "ABOVE_VAH")
        self.assertEqual(by_key["e2"]["continuation_hypothesis_label"], "BULLISH")

    def test_loader_accepts_v3_while_preserving_v2_compatibility(self) -> None:
        row = event("v3-event", 1_700_000_095)
        row.update({
            "schema_version": "order-flow-evidence-v3",
            "signed_tick_pressure": "4", "positive_tick_count": "5", "negative_tick_count": "1",
            "price_progress": "0.0004", "prior_high": "1.1000", "prior_low": "1.0900",
            "bar_close": "1.1010", "atr": "0.0010", "pressure_progress_divergence": "false",
            "continuation_hypothesis": "1", "reversal_hypothesis": "0",
            "auction_context_available": "true", "value_area_poc": "1.0950",
            "value_area_vah": "1.1000", "value_area_val": "1.0900",
            "value_area_source_quality": "0.75", "value_area_source": "2", "auction_location": "2",
        })
        loaded, rejected = load_order_flow_events([row])
        self.assertEqual(len(loaded), 1)
        self.assertEqual(rejected, {})
        self.assertEqual(loaded[0]["schema_version"], "order-flow-evidence-v3")

if __name__ == "__main__":
    unittest.main()
