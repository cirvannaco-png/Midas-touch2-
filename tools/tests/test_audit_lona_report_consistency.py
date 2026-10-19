"""Tests for tranche-versus-position-group LONA report reconciliation."""
from __future__ import annotations

import unittest

from tools.audit_lona_report_consistency import audit, reconcile_report


def make_report(group_count: int = 30) -> dict:
    rows = [
        {
            "entry_time": f"2026-01-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z",
            "exit_time": f"2026-02-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z",
            "direction": "LONG" if i % 2 == 0 else "SHORT",
            "pnl": 2.0 if i % 2 == 0 else -1.0,
            "quantity": 0.1,
            "entry_price": 100.0,
            "exit_price": 101.0,
        }
        for i in range(group_count)
    ]
    commission_rate = 0.0005
    net_pnl = sum(row["pnl"] for row in rows) - sum(
        commission_rate * row["quantity"] * (row["entry_price"] + row["exit_price"])
        for row in rows
    )
    return {
        "report_id": "fixture-report",
        "strategy_id": "fixture-strategy",
        "symbol": "XAUUSD",
        "timeframe": "1d",
        "stored_metrics": {
            "trade_count": group_count * 3,
            "trade_count_unit": "closed_tranche",
            "net_pnl": round(net_pnl, 8),
            "win_rate_pct": 50.0,
            "profit_factor": 2.0,
            "expectancy": net_pnl / (group_count * 3),
            "max_drawdown_pct": 1.5,
        },
        "trade_history": {
            "rows": rows,
            "reconstructed_count": group_count,
            "reconstructed_total": group_count,
            "has_next": False,
            "raw_export_complete": True,
            "grouping": {
                "history_unit": "position_group",
                "tranches_per_group": 3,
                "unit_semantics_evidence": (
                    "The strategy opens three parent tranches per setup; stored report "
                    "count is closed tranches and reconstructed rows are position groups."
                ),
            },
        },
        "simulation": {"initial_cash": 10000.0, "commission_rate": commission_rate},
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
    def test_complete_history_reconciles_but_is_not_profitability_proof(self):
        result = reconcile_report(make_report(), min_groups=30)
        self.assertTrue(result["history_reconciled"])
        self.assertTrue(result["optimization_allowed"])
        self.assertEqual(
            result["interpretation"],
            "RECONCILED_AND_ELIGIBLE_FOR_HUMAN_REVIEW_NOT_PROOF_OF_PROFITABILITY",
        )
        history = result["reconstructed_history"]
        self.assertEqual(history["position_group_count"], 30)
        self.assertEqual(history["group_level_metrics"]["group_count"], 30)
        self.assertAlmostEqual(
            history["group_level_metrics"]["net_pnl_after_report_simulated_commission"],
            result["stored_metrics"]["net_pnl"],
            places=7,
        )
        self.assertTrue(history["unit_relationship_verified"])
        self.assertTrue(history["aggregate_net_pnl_reconciled"])

    def test_three_to_one_tranche_group_ratio_is_reconciled_not_misreported_as_missing(self):
        report = make_report(9)
        result = reconcile_report(report, min_groups=30)
        self.assertTrue(result["history_reconciled"])
        self.assertEqual(result["reconciliation_blockers"], [])
        self.assertFalse(result["optimization_allowed"])
        self.assertIn(
            "BELOW_MINIMUM_POSITION_GROUP_COUNT_FOR_PERFORMANCE_REVIEW",
            result["promotion_blockers"],
        )
        self.assertEqual(result["reconstructed_history"]["position_group_count"], 9)
        self.assertEqual(result["stored_metrics"]["trade_count"], 27)

    def test_actual_count_mismatch_blocks_reconciliation(self):
        report = make_report(9)
        report["stored_metrics"]["trade_count"] = 28
        result = reconcile_report(report)
        self.assertFalse(result["history_reconciled"])
        self.assertIn("TRADE_UNIT_SEMANTICS_NOT_RECONCILED", result["reconciliation_blockers"])
        self.assertFalse(result["optimization_allowed"])

    def test_missing_or_incomplete_history_blocks_reconciliation(self):
        report = make_report(30)
        report["trade_history"]["raw_export_complete"] = False
        report["trade_history"]["has_next"] = True
        result = reconcile_report(report)
        self.assertFalse(result["history_reconciled"])
        self.assertIn("RECONSTRUCTED_HISTORY_HAS_NEXT_OR_UNKNOWN", result["reconciliation_blockers"])
        self.assertIn("COMPLETE_GROUP_HISTORY_EXPORT_NOT_AVAILABLE", result["reconciliation_blockers"])

    def test_unverified_broker_costs_block_optimization(self):
        report = make_report()
        report["costs"]["verified"] = False
        report["costs"]["slippage"] = False
        result = reconcile_report(report)
        self.assertTrue(result["history_reconciled"])
        self.assertFalse(result["optimization_allowed"])
        self.assertIn("TRANSACTION_COSTS_NOT_BROKER_VERIFIED", result["promotion_blockers"])

    def test_zero_trade_report_is_not_performance_evidence(self):
        report = make_report(0)
        report["stored_metrics"]["trade_count"] = 0
        report["stored_metrics"]["net_pnl"] = 0.0
        report["stored_metrics"]["win_rate_pct"] = 0.0
        report["stored_metrics"]["profit_factor"] = 0.0
        report["trade_history"]["reconstructed_count"] = 0
        report["trade_history"]["reconstructed_total"] = 0
        report["trade_history"]["rows"] = []
        result = reconcile_report(report)
        self.assertTrue(result["history_reconciled"])
        self.assertFalse(result["optimization_allowed"])
        self.assertIn("ZERO_POSITION_GROUPS_NO_PERFORMANCE_EVIDENCE", result["promotion_blockers"])

    def test_manifest_blocks_promotion_if_any_report_is_not_certified(self):
        good = make_report()
        bad = make_report(1)
        bad["report_id"] = "small-sample"
        result = audit({
            "schema_version": 1,
            "reports": [good, bad],
            "min_groups_for_performance_review": 30,
            "net_pnl_reconciliation_tolerance": 0.02,
        })
        self.assertFalse(result["optimization_allowed"])
        self.assertEqual(result["history_reconciled_report_count"], 2)
        self.assertEqual(result["unreconciled_report_count"], 0)
        self.assertEqual(result["promotion_blocked_report_count"], 1)


if __name__ == "__main__":
    unittest.main()
