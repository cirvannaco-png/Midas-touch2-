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

    def test_live_routing_remains_unchanged_until_shadow_telemetry_is_integrated(self):
        source = read("EA/includes/Trading/StrategyTradeZone.mqh")
        main = read("EA/MedisTouch_v2.8.mq5")
        # This PR adds passive helper classes only. Wiring belongs in a
        # separately reviewed change because it touches the live EA source.
        self.assertNotIn("RegimeShadowLogger", source)
        self.assertNotIn("InpEnableRegimeShadowLogging", main)
        self.assertNotIn("InpEnableBrokerAwareEntryGate", main)
        self.assertNotIn("m_regimeShadowLogger.Log", source)

    def test_rollover_window_is_telemetry_only_and_validated(self):
        logger = read("EA/includes/Decision/RegimeShadowLogger.mqh")
        self.assertIn("ConfigureRolloverTelemetry", logger)
        self.assertIn("startHour<0 || startHour>23", logger)
        self.assertIn("m_rolloverStartMinute==m_rolloverEndMinute", logger)
        self.assertIn("IN_CONFIGURED_WINDOW_TELEMETRY_ONLY", logger)
        # No timing input or live routing hook is added in this additive port.
        decision = read("EA/includes/Trading/StrategyTradeZone.mqh")
        main = read("EA/MedisTouch_v2.8.mq5")
        self.assertNotIn("ConfigureRegimeRolloverTelemetry", decision)
        self.assertNotIn("InpRolloverShadowWindowEnabled", main)

    def test_overnight_broker_schedule_respects_current_vs_previous_day(self):
        source = read("EA/includes/Core/BrokerMarketAvailability.mqh")
        self.assertIn("bool Contains(datetime from,datetime to,long nowSeconds,bool sessionStartsToday)", source)
        self.assertIn("if(sessionStartsToday) return (nowSeconds>=start);", source)
        self.assertIn("return (nowSeconds<finish);", source)
        self.assertIn("BROKER_SCHEDULE_NOT_EXPOSED_BY_TERMINAL", source)

    def test_broker_aware_entry_gate_is_separate_and_default_off(self):
        policy = read("EA/includes/Decision/MarketConditionsPolicy.mqh")
        main = read("EA/MedisTouch_v2.8.mq5")
        # Policy is unit-testable but not wired into trade eligibility here.
        self.assertNotIn("InpEnableBrokerAwareEntryGate", main)
        self.assertNotIn("InpBrokerGateMaxSpreadPoints", main)
        self.assertNotIn("InpBrokerGateMaxSpreadToATR", main)
        self.assertIn("BLOCK_INVALID_OR_INCOMPLETE_POLICY_CONFIGURATION", policy)
        self.assertIn("BLOCK_MARKET_AVAILABILITY_", policy)
        self.assertIn("BLOCK_LIQUIDITY_SESSION_POLICY", policy)
        self.assertIn("BLOCK_MAX_SPREAD_POINTS", policy)
        self.assertIn("BLOCK_MAX_SPREAD_TO_ATR", policy)
        self.assertIn("BLOCK_CONFIGURED_ROLLOVER_WINDOW", policy)
        self.assertIn("BLOCK_LOW_VOLATILITY", policy)
        self.assertIn("BLOCK_UNDEFINED_VOLATILITY", policy)
        self.assertNotIn("OrderSend(", policy)
        self.assertNotIn("trade.Buy(", policy)
        self.assertNotIn("if(InpEnableBrokerAwareEntryGate)", main)
        self.assertNotIn("BROKER_CONDITIONS_REJECTED", main)

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
