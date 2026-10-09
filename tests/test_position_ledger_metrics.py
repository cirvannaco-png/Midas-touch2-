import unittest
from datetime import datetime, timezone

from tools.position_ledger_metrics import calculate_metrics, reconstruct_positions


def deal(pid, stamp, entry, volume, profit=0.0, commission=0.0, risk_cash=0.0, lane="A", row=2):
    return {
        "position_id": str(pid), "time": datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc),
        "entry": entry, "volume": volume, "profit": profit, "commission": commission,
        "swap": 0.0, "fee": 0.0, "risk_cash": risk_cash, "lane": lane, "source_row": row,
    }


class PositionLedgerMetricsTests(unittest.TestCase):
    def test_partial_exits_are_one_position_and_costs_are_net(self):
        rows = [
            deal(100, "2026-01-01T10:00:00", "in", 1.0, commission=-1.0, risk_cash=100, row=2),
            deal(100, "2026-01-01T11:00:00", "out", 0.4, profit=30.0, commission=-0.3, risk_cash=100, row=3),
            deal(100, "2026-01-01T12:00:00", "out", 0.6, profit=20.0, commission=-0.3, risk_cash=100, row=4),
        ]
        positions, ignored = reconstruct_positions(rows)
        report = calculate_metrics(positions, 10000, ignored)
        self.assertEqual(len(positions), 1)
        self.assertEqual(report["partial_exit_rows_collapsed"], 1)
        self.assertAlmostEqual(report["net_pnl"], 48.4)
        self.assertAlmostEqual(report["account_return_pct"], 0.484)
        self.assertAlmostEqual(report["average_realized_R"], 0.484)

    def test_incomplete_trade_is_not_counted(self):
        positions, ignored = reconstruct_positions([deal(200, "2026-01-01T10:00:00", "in", 1.0, row=2)])
        self.assertEqual(positions, [])
        self.assertEqual(ignored["incomplete_volume"], 1)
        self.assertEqual(calculate_metrics(positions, 10000)["status"], "no_complete_positions")

    def test_metrics_and_closed_position_drawdown(self):
        rows = [
            deal(1, "2026-01-01T09:00:00", "in", 1, risk_cash=100, row=2),
            deal(1, "2026-01-01T10:00:00", "out", 1, profit=50, risk_cash=100, row=3),
            deal(2, "2026-01-02T09:00:00", "in", 1, risk_cash=100, row=4),
            deal(2, "2026-01-02T10:00:00", "out", 1, profit=-25, risk_cash=100, row=5),
        ]
        positions, ignored = reconstruct_positions(rows)
        report = calculate_metrics(positions, 1000, ignored)
        self.assertEqual(report["completed_positions"], 2)
        self.assertAlmostEqual(report["net_pnl"], 25)
        self.assertAlmostEqual(report["account_return_pct"], 2.5)
        self.assertEqual(report["profit_factor"], 2.0)
        self.assertEqual(report["average_win"], 50)
        self.assertEqual(report["average_loss"], -25)
        self.assertEqual(report["max_closed_position_drawdown_cash"], 25)
        self.assertEqual(report["target_reached"], None)

    def test_currently_open_ids_are_excluded(self):
        rows = [deal(3, "2026-01-01T09:00:00", "in", 1, row=2),
                deal(3, "2026-01-01T10:00:00", "out", 1, profit=12, row=3)]
        positions, ignored = reconstruct_positions(rows, {"3"})
        self.assertEqual(positions, [])
        self.assertEqual(ignored["open_position"], 1)

    def test_netting_reversal_is_explicitly_ambiguous(self):
        rows = [deal(4, "2026-01-01T09:00:00", "in", 1, row=2),
                deal(4, "2026-01-01T10:00:00", "inout", 1.5, profit=8, row=3)]
        positions, ignored = reconstruct_positions(rows)
        self.assertEqual(positions, [])
        self.assertEqual(ignored["inout_ambiguous"], 1)


if __name__ == "__main__":
    unittest.main()
