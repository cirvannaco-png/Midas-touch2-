"""Source-level regression checks for the opt-in MTF trailing candidate.

These checks guard wiring/look-ahead regressions; they do NOT replace MetaTrader
Strategy Tester validation or prove profitable/live execution.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
INPUTS = (ROOT / "EA/includes/Execution/DynamicStopInputs.mqh").read_text(encoding="utf-8")
MANAGER = (ROOT / "EA/includes/Execution/PositionManager.mqh").read_text(encoding="utf-8")
ENGINE = (ROOT / "EA/includes/Execution/DynamicStopEngine.mqh").read_text(encoding="utf-8")


class HigherTimeframeTrailingSourceTests(unittest.TestCase):
    def test_feature_is_opt_in_until_matched_mt5_validation(self):
        self.assertIn("InpDynamicStopUseHTFReferenceLevels = false", INPUTS)
        self.assertIn("InpDynamicStopUseWeeklyReference = true", INPUTS)
        self.assertIn("InpDynamicStopUseMonthlyReference = true", INPUTS)

    def test_only_previous_completed_week_and_month_are_used(self):
        self.assertIn("iTime(symbol,PERIOD_W1,1)", MANAGER)
        self.assertIn("iLow(symbol,PERIOD_W1,1)", MANAGER)
        self.assertIn("iHigh(symbol,PERIOD_W1,1)", MANAGER)
        self.assertIn("iTime(symbol,PERIOD_MN1,1)", MANAGER)
        self.assertIn("iLow(symbol,PERIOD_MN1,1)", MANAGER)
        self.assertIn("iHigh(symbol,PERIOD_MN1,1)", MANAGER)
        # A reference at shift zero would use the still-forming candle.
        self.assertNotIn("iLow(symbol,PERIOD_W1,0)", MANAGER)
        self.assertNotIn("iHigh(symbol,PERIOD_W1,0)", MANAGER)
        self.assertNotIn("iLow(symbol,PERIOD_MN1,0)", MANAGER)
        self.assertNotIn("iHigh(symbol,PERIOD_MN1,0)", MANAGER)

    def test_reference_direction_and_distance_are_gated(self):
        self.assertIn("isBuy ? iLow(symbol,PERIOD_W1,1) : iHigh(symbol,PERIOD_W1,1)", MANAGER)
        self.assertIn("isBuy ? iLow(symbol,PERIOD_MN1,1) : iHigh(symbol,PERIOD_MN1,1)", MANAGER)
        self.assertIn("InpDynamicStopHTFMaxDistanceATR*atr", MANAGER)
        self.assertIn("InpDynamicStopUseHTFReferenceLevels", MANAGER)

    def test_existing_stop_safety_gates_remain_in_engine(self):
        self.assertIn("BrokerDistanceSafe(symbol,isBuy,candidate,currentPrice)", ENGINE)
        self.assertIn("IsTighter(isBuy,candidate,currentSL)", ENGINE)
        self.assertIn("ImprovementLargeEnough(symbol,candidate,currentSL)", ENGINE)
        self.assertIn("spread protection", ENGINE)


if __name__ == "__main__":
    unittest.main()
