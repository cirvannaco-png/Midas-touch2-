"""Tests for tools.audit_lona_report_consistency."""
from __future__ import annotations

import unittest

from tools.audit_lona_report_consistency import audit, reconcile_report


def make_report(count: int = 30) -> dict:
    rows = [
        {
            "entry_time": f"2026-01-01T00:{i:02d}:00Z",
            "exit_time": f"2026-02-01T01:{i:02d}:00Z",
            "direction": "LONG" if i % 2 == 0 else "SHORT",
            "pnl": 2.0 if i % 2 == 0 else -1.0,
        }
        for i in range(count)
    ]
    return {
        "report_id": "fixture-report",
        "strategy_id": "fixture-strategy",
        "symbol": "XAUUSD",
        "timeframe": "1d",
        "stored_metrics": {
            "trade_count": count,
            "net_pnl": 15.0,
            "win_rate_pct": 50.0,
            "profit_factor": 2.0,
            "expectancy": 0.5,
            "max_drawdown_pct": 1.5,
        },
        "trade_history": {
            "rows": rows,
            "reconstructed_count": count,
            "reconstructed_total": count,
            "has_next": False,
            "raw_export_complete": True,
            "legacy_redacted": False,
        },
        "costs": {
            "verified": True,
            "commission": True,
            "swap": True,
            "spread": True,
            "slippage": True,
            "broker_fees": True,
            "evidence_reference": "sha256:verified-broker-costs",
        },
    }


class LonaReportConsistencyTests(unittest.TestCase):
    def test_complete_reconciled_history_can_pass_to_human_review(self):
        result = reconcile_report(make_report(), min_trades=30)
        self.assertTrue(result["optimization_allowed"])
        self.assertEqual(result["interpretation"], "ELIGIBLE_FOR_HUMAN_REVIEW_NOT_PROOF_OF_PROFITABILITY")
        self.assertEqual(result["reconstructed_history"]["gross_pnl_sum"], 15.0)
        self.assertTrue(result["reconstructed_history"]["win_rate_is_complete_sample"])
        self.assertTrue(any("NOT_COMPARED_TO_STORED_NET_PNL" in w for w in result["warnings"]))

    def test_count_mismatch_blocks_optimization_even_if_endpoint_has_no_next_page(self):
        report = make_report()
        report["stored_metrics"]["trade_count"] = 27
        report["trade_history"]["reconstructed_count"] = 9
        report["trade_history"]["reconstructed_total"] = 9
        report["trade_history"]["rows"] = report["trade_history"]["rows"][:9]
        result = reconcile_report(report)
        self.assertFalse(result["optimization_allowed"])
        self.assertIn("STORED_AND_RECONSTRUCTED_TRADE_COUNTS_DIFFER", result["blockers"])
        self.assertFalse(result["reconstructed_history"]["win_rate_is_complete_sample"])

    def test_unverified_costs_block_optimization(self):
        report = make_report()
        report["costs"]["verified"] = False
        report["costs"]["slippage"] = False
        result = reconcile_report(report)
        self.assertIn("TRANSACTION_COSTS_NOT_FULLY_VERIFIED", result["blockers"])
        self.assertFalse(result["optimization_allowed"])

    def test_100_percent_win_rate_and_zero_profit_factor_requires_review(self):
        report = make_report()
        report["stored_metrics"]["win_rate_pct"] = 100
        report["stored_metrics"]["profit_factor"] = 0
        result = reconcile_report(report)
        self.assertIn("STORED_METRIC_INCONSISTENCY_REQUIRES_EXPLANATION", result["blockers"])

    def test_zero_trade_report_is_not_performance_evidence(self):
        report = make_report(0)
        report["stored_metrics"]["trade_count"] = 0
        report["trade_history"]["reconstructed_count"] = 0
        report["trade_history"]["reconstructed_total"] = 0
        report["trade_history"]["rows"] = []
        result = reconcile_report(report)
        self.assertIn("ZERO_TRADES_NO_PERFORMANCE_EVIDENCE", result["blockers"])
        self.assertFalse(result["optimization_allowed"])

    def test_manifest_blocks_promotion_if_any_report_is_incomplete(self):
        good = make_report()
        bad = make_report()
        bad["report_id"] = "incomplete"
        bad["stored_metrics"]["trade_count"] = 3
        bad["trade_history"]["rows"] = bad["trade_history"]["rows"][:1]
        bad["trade_history"]["reconstructed_count"] = 1
        bad["trade_history"]["reconstructed_total"] = 1
        result = audit({"schema_version": 1, "reports": [good, bad]})
        self.assertFalse(result["optimization_allowed"])
        self.assertEqual(result["blocked_report_count"], 1)


if __name__ == "__main__":
    unittest.main()
