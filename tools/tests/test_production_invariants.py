from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
TRACKER = ROOT / "EA" / "includes" / "Trading" / "OutcomeTracker.mqh"
CI = ROOT / ".gitlab-ci.yml"


def test_outcome_tracker_has_real_add_setup_definition():
    text = TRACKER.read_text()
    assert "void COutcomeTracker::AddSetup(TradeSetup &setup, long decisionId)" in text
    assert "void COutcomeTracker::AddSetup(TradeSetup &setup, long decisionId)\n  {" in text


def test_outcome_tracker_uses_decision_id_for_fill_identity():
    text = TRACKER.read_text()
    assert "GetFillState(datetime creation_time, long decisionId" in text
    assert "m_pending[i].decisionId != decisionId" in text


def test_outcome_tracker_is_execution_timeframe_only():
    text = TRACKER.read_text()
    assert "executionCtx" in text
    assert "executionCtx.candles.Timeframe() != m_entryTF" in text
    assert "The setup's creation bar is never eligible" in text


def test_ea_initializes_tracker_on_chart_execution_timeframe():
    text = EA.read_text()
    assert "g_tracker.Init(&g_logger,_Symbol,_Period" in text
    assert "g_tracker.Update(g_chartCtx);" in text
    assert "g_tracker.Update(g_fvgCtx);" not in text


def test_lifecycle_lookup_uses_creation_time_and_decision_id():
    text = EA.read_text()
    assert "g_tracker.GetFillState(g_lifecycleCreationTime,g_lifecycleDecisionId" in text


def test_ci_runs_core_gates_on_main():
    text = CI.read_text()
    assert 'if: \'$CI_COMMIT_BRANCH == "main"\'' in text
    assert "mql5-structure:" in text
    assert "medis-touch-python:" in text
    assert "telegram-bridge:" in text
    assert "telegram-bridge-dependency-audit:" in text
