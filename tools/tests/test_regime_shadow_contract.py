"""Contract tests for the passive regime/session shadow instrumentation."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relpath: str) -> str:
    path = ROOT / relpath
    if not path.is_file():
        raise AssertionError(f"required implementation file missing: {relpath}")
    return path.read_text(encoding="utf-8")


class RegimeShadowContractTests(unittest.TestCase):
    def test_shadow_logger_records_separate_market_dimensions(self):
        source = read("EA/includes/Decision/RegimeShadowLogger.mqh")
        for field in (
            '"Regime"',
            '"VolatilityRegime"',
            '"MarketPhase"',
            '"SelectedStrategy"',
            '"SelectionStatus"',
            '"RejectionReason"',
            '"LiquiditySession"',
            '"BrokerMarketAvailability"',
            '"SpreadAssessment"',
            '"SpreadToATR"',
            '"RolloverStatus"',
            '"SignalID"',
            '"EntryReference"',
            '"ThesisInvalidation"',
            '"ProtectiveStop"',
        ):
            with self.subTest(field=field):
                self.assertIn(field, source)

    def test_shadow_logger_is_observational_not_an_execution_component(self):
        logger = read("EA/includes/Decision/RegimeShadowLogger.mqh")
        availability = read("EA/includes/Core/BrokerMarketAvailability.mqh")
        self.assertNotIn("OrderSend(", logger)
        self.assertNotIn("g_router", logger)
        self.assertNotIn("CTradeDecision", logger)
        self.assertNotIn("OrderSend(", availability)
        self.assertNotIn("trade.Buy(", availability)
        self.assertNotIn("trade.Sell(", availability)

    def test_setup_generation_logs_rejections_and_does_not_gate_on_shadow_flag(self):
        source = read("EA/includes/Trading/StrategyTradeZone.mqh")
        main = read("EA/MedisTouch_v2.8.mq5")
        self.assertIn("REGIME_UNDEFINED_FAIL_CLOSED", source)
        self.assertIn("SELECTED_STRATEGY_BUILDER_FAILED", source)
        self.assertIn("SMC_SETUP_BUILD_FAILED", source)
        self.assertIn("m_regimeShadowLogger.Log", source)
        self.assertIn("InpEnableRegimeShadowLogging=true", main)
        self.assertIn("ConfigureRegimeShadowLogger(InpEnableRegimeShadowLogging)", main)
        self.assertIn("RISK_VALIDATED_CANDIDATE", main)
        self.assertIn("RISK_VALIDATION_FAILED", main)
        self.assertIn("DIRECTIONAL_ADVANTAGE_BELOW_MINIMUM", main)
        self.assertIn("POLICY_AUTHORIZED", main)
        self.assertIn("POLICY_REJECTED", main)
        # The input is passed to the observer; it is not a conditional around
        # the executable setup selection / order-routing path.
        self.assertNotIn("if(InpEnableRegimeShadowLogging)", main)

    def test_rollover_window_is_telemetry_only_and_validated(self):
        logger = read("EA/includes/Decision/RegimeShadowLogger.mqh")
        decision = read("EA/includes/Trading/StrategyTradeZone.mqh")
        main = read("EA/MedisTouch_v2.8.mq5")
        self.assertIn("ConfigureRolloverTelemetry", logger)
        self.assertIn("startHour<0 || startHour>23", logger)
        self.assertIn("m_rolloverStartMinute==m_rolloverEndMinute", logger)
        self.assertIn("ConfigureRegimeRolloverTelemetry", decision)
        self.assertIn("InpRolloverShadowWindowEnabled=false", main)
        self.assertIn("ConfigureRegimeRolloverTelemetry(InpRolloverShadowWindowEnabled", main)
        self.assertIn("IN_CONFIGURED_WINDOW_TELEMETRY_ONLY", logger)

    def test_overnight_broker_schedule_respects_current_vs_previous_day(self):
        source = read("EA/includes/Core/BrokerMarketAvailability.mqh")
        self.assertIn("bool Contains(datetime from,datetime to,long nowSeconds,bool sessionStartsToday)", source)
        self.assertIn("if(sessionStartsToday) return (nowSeconds>=start);", source)
        self.assertIn("return (nowSeconds<finish);", source)
        self.assertIn("BROKER_SCHEDULE_NOT_EXPOSED_BY_TERMINAL", source)

    def test_existing_outcome_export_contains_join_key_and_cost_fields(self):
        source = read("EA/includes/Core/SignalLogger.mqh")
        outcome = source[source.index("bool CSignalLogger::LogOutcome"):]
        for field in (
            '"SignalID"',
            '"RealizedNetPnL"',
            '"Commission"',
            '"SpreadCost"',
            '"SlippageCost"',
            '"OutcomeEpoch"',
            '"Regime"',
            '"SelectedStrategy"',
        ):
            with self.subTest(field=field):
                self.assertIn(field, outcome)


if __name__ == "__main__":
    unittest.main()
