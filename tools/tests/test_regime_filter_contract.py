"""Source contracts for the opt-in trend-vs-chop entry filter."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = (ROOT / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
SCORING = (ROOT / "EA/includes/Analysis/Scoring.mqh").read_text(encoding="utf-8")
REGIME = (ROOT / "EA/includes/Regime/RegimeDetector.mqh").read_text(encoding="utf-8")
PHASE = (ROOT / "EA/includes/SmartMoney/MarketPhase.mqh").read_text(encoding="utf-8")


def test_trend_regime_filter_is_off_by_default_and_wired():
    assert "input bool InpRequireTrendingRegime=false;" in EA
    assert "ConfigureRegimeFilter(InpRequireTrendingRegime)" in EA
    assert "m_requireTrendingRegime(false)" in SCORING


def test_enabled_filter_fails_closed_unless_regime_is_trending():
    assert "if(m_requireTrendingRegime && m_regimeDetector.Classify(1) != REGIME_TRENDING)" in SCORING
    assert "closedBarShift<1" in REGIME
    assert "m_volRegime.Classify(closedBarShift)" in REGIME


def test_market_phase_uses_only_completed_candles():
    assert "m_candles.GetATR(1)" in PHASE
    assert "for(int i = 1; i <= m_rangeLookback; i++)" in PHASE
    assert "for(int i = 1; i <= MathMin(3, m_sweepRecencyBars); i++)" in PHASE
    assert "ev.bar_index >= 1" in PHASE
