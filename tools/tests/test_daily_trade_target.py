from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
TARGET = ROOT / "EA" / "includes" / "Trading" / "DailyTradeTarget.mqh"
TRACKER = ROOT / "EA" / "includes" / "Trading" / "OutcomeTrackerLive.mqh"


def test_daily_target_counts_qualified_completed_outcomes_not_entries():
    ea = EA.read_text()
    target = TARGET.read_text()
    tracker = TRACKER.read_text()

    assert "InpMinimumQualifiedTradesPerDay=3;" in ea
    assert "InpMinimumQualifiedTradeR=0.25;" in ea
    assert "OnQualifiedClose(datetime at,double realizedR,ulong positionId)" in target
    assert "g_dailyTradeTarget.OnExecution" not in ea
    assert "OnExecution(" not in target
    assert "if(tracked && !stillOpen && g_tracker.LastFinalizedQualified())" in ea
    assert "m_lastFinalizedQualified=(sized&&coarseOutcome==\"win\"" in tracker
    assert "realizedR+1e-9<m_minQualifiedR" in target


def test_target_is_weekday_only_and_persists_across_restarts():
    target = TARGET.read_text()

    assert "t.day_of_week>=1 && t.day_of_week<=5" in target
    assert "DateKey(at)!=m_dateKey" in target
    assert "GlobalVariableSet(m_storageKey+\".D\"" in target
    assert "GlobalVariableSet(m_storageKey+\".C\"" in target
    assert "GlobalVariableCheck(m_storageKey+\".C\")" in target
    assert "AccountInfoInteger(ACCOUNT_LOGIN)" in target
    assert "SyncStoredState();return;" in target
    assert "GlobalVariablesFlush();" in target
    assert "GlobalVariableCheck(countedKey)" in target
    assert "QualifiedKey(ulong positionId)" in target
    assert "m_lastPositionId" not in target
    assert "markerWrite==0" in target
    assert "trade not counted." in target
    assert "GlobalVariablesFlush();" in target
    assert "markerWrite==0" in target
    assert "GlobalVariableCheck(countedKey)" in target


def test_entry_dealing_costs_are_included_before_qualification():
    ea = EA.read_text()
    tracker = TRACKER.read_text()

    assert "g_tracker.RecordExecutionCosts(decisionId,entryCommission,entrySwap,entryFee)" in ea
    assert "p.realizedPnL+=commission+swap+fee" in tracker
    assert "LastFinalizedR()const{return m_lastFinalizedR;}" in tracker
    assert "No trades were forced." in TARGET.read_text()
    assert "g_dailyTradeTarget.Init(InpMinimumQualifiedTradesPerDay,InpMinimumQualifiedTradeR,InpMagicNumber)" in ea
