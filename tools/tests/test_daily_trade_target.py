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
    assert "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in ea
    assert "Live trade outcome attribution/learning" in ea
    assert "g_dailyTradeTarget.Init(g_tradeOutcomeTrackingEnabled?InpMinimumQualifiedTradesPerDay:0" in ea
    assert "if(g_tradeOutcomeTrackingEnabled && decisionId>0 && g_tracker.MarkExecuted" in ea
    assert "if(!g_tradeOutcomeTrackingEnabled)return;" in ea
    assert "OnQualifiedClose(datetime at,double realizedR,ulong positionId)" in target
    assert "g_dailyTradeTarget.OnExecution" not in ea
    assert "OnExecution(" not in target
    assert "tracked && !stillOpen && g_tracker.LastFinalizedQualified()" in ea
    assert 'm_lastFinalizedQualified=(sized&&coarseOutcome=="win"' in tracker
    assert "realizedR+1e-9<m_minQualifiedR" in target
    assert "No trades were forced." in target


def test_target_is_weekday_only_and_daily_state_survives_restarts():
    target = TARGET.read_text()

    assert "t.day_of_week>=1 && t.day_of_week<=5" in target
    assert 'return m_storageKey+".C."+IntegerToString(dateKey);' in target
    assert 'return m_storageKey+".B."+IntegerToString(dateKey);' in target
    assert 'legacyDateKey=m_storageKey+".D"' in target
    assert 'legacyCountKey=m_storageKey+".C"' in target
    assert "EnsureBaselineLocked(dateKey)" in target
    assert "GlobalVariableSet(CountKey(dateKey),(double)currentCount)" in target
    assert "GlobalVariablesFlush();" in target
    assert "m_reconcilePending=false" in target
    assert "if(m_reconcilePending || !GlobalVariableCheck(key))" in target
    assert "GlobalVariablesFlush();\n\n      if(!EnsureBaselineLocked(closeDateKey))" in target
    assert "AccountInfoInteger(ACCOUNT_LOGIN)" in target
    assert "SyncStoredState();" in target


def test_counter_serializes_updates_and_deduplicates_closes():
    target = TARGET.read_text()

    assert 'm_storageKey+".X."+StringFormat("%I64u",positionId)' in target
    assert "GlobalVariableTemp(m_lockKey)" in target
    assert "!created && !GlobalVariableCheck(m_lockKey)" in target
    assert "GlobalVariableSetOnCondition(m_lockKey,token,0.0)" in target
    assert "GetTickCount64()" in target
    assert "now-held>30000.0" in target
    assert "now-m_legacyLockSeenAt>30000.0" in target
    assert "GlobalVariableSetOnCondition(m_lockKey,0.0,m_lockValue)" in target
    assert "if(GlobalVariableCheck(marker))" in target
    assert "GlobalVariableSet(marker,(double)at)" in target
    assert "CountMarkersForDateLocked(closeDateKey)" in target
    assert "MigrateLegacyLastPositionLocked()" in target
    assert "GlobalVariableDel(legacyKey);" in target
    assert "m_lastPositionId" not in target


def test_restart_reconciliation_and_marker_retention_are_bounded():
    target = TARGET.read_text()

    assert "DateKey((datetime)storedAt)==dateKey" in target
    assert "if(storedAt<1000000000.0 || storedAt<cutoff)" in target
    assert "90*86400" in target
    assert "GlobalVariableDel(name)" in target
    assert "The marker is the durable idempotency record" in target


def test_entry_dealing_costs_are_included_before_qualification():
    ea = EA.read_text()
    tracker = TRACKER.read_text()

    assert "g_tracker.RecordExecutionCosts(decisionId,entryCommission,entrySwap,entryFee)" in ea
    assert "p.realizedPnL+=commission+swap+fee" in tracker
    assert "LastFinalizedR()const{return m_lastFinalizedR;}" in tracker
