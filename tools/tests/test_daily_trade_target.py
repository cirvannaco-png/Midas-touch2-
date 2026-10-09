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


def test_weekday_counter_persists_and_serializes_cross_symbol_updates():
    target = TARGET.read_text()

    assert "t.day_of_week>=1 && t.day_of_week<=5" in target
    assert "DateKey(at)!=m_dateKey" in target
    assert "CounterKey(int dateKey)" in target
    assert "GlobalVariableTemp(m_lockKey)" in target
    assert "GlobalVariableSetOnCondition(m_lockKey,now,0.0)" in target
    assert "GlobalVariableSetOnCondition(m_lockKey,now,observed)" in target
    assert "GlobalVariableSetOnCondition(m_lockKey,0.0,token)" in target
    assert "Under the shared lock, marker and counter writes are serialized" in target
    assert "GlobalVariableCheck(countedKey)" in target
    assert "QualifiedKey(ulong positionId)" in target
    assert "GlobalVariablesFlush();" in target
    assert "dateWrite==0 || countWrite==0" not in target
    assert "countWrite==0" in target
    assert "InitializeCurrentDayState()" in target
    assert "GlobalVariableCheck(m_storageKey+\".D\")" in target
    assert "GlobalVariableCheck(m_storageKey+\".C\")" in target
    assert "AccountInfoInteger(ACCOUNT_LOGIN)" in target
    assert "m_lastPositionId" not in target
    assert "trade not counted." in target


def test_entry_costs_are_included_before_qualification_and_source_is_well_formed():
    ea = EA.read_text()
    tracker = TRACKER.read_text()
    target = TARGET.read_text()

    assert "g_tracker.RecordExecutionCosts(decisionId,entryCommission,entrySwap,entryFee)" in ea
    assert "p.realizedPnL+=commission+swap+fee" in tracker
    assert "LastFinalizedR()const{return m_lastFinalizedR;}" in tracker
    assert "No trades were forced." in target
    assert "g_dailyTradeTarget.Init(InpMinimumQualifiedTradesPerDay,InpMinimumQualifiedTradeR,InpMagicNumber)" in ea
    # Catch literal backslash-n tokens that are invalid in normal MQL source.
    assert "\\n" not in ea
    assert "\\n" not in tracker
    assert "\\n" not in target
