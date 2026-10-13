from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "EA" / "includes" / "Trading" / "OutcomeTrackerLive.mqh"
CONFIG = ROOT / "EA" / "includes" / "Core" / "Config.mqh"
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"


def test_live_accounting_deduplicates_stable_broker_deal_tickets():
    tracker = TRACKER.read_text(encoding="utf-8")
    ea = EA.read_text(encoding="utf-8")
    assert "DealAlreadyProcessed(ulong dealTicket)" in tracker
    assert "RememberDeal(ulong dealTicket)" in tracker
    assert "if(DealAlreadyProcessed(dealTicket)) return true;" in tracker
    assert "MarkExecuted(decisionId,price,dealTime,volume,trans.deal" in ea
    assert "outcome,trans.deal,volume,true" in ea


def test_entry_and_exit_cashflows_are_net_and_signed_separately():
    tracker = TRACKER.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    ea = EA.read_text(encoding="utf-8")
    assert "double nextPnL=p.realizedPnL+commission+swap+fee;" in tracker
    assert "p.realizedPnL=nextPnL;" in tracker
    assert "double nextPnL=p.realizedPnL+netPnl;" in tracker
    assert "p.realizedPnL=nextPnL;" in tracker
    assert "totalCommissionCashflow" in config
    assert "totalSwapCashflow" in config
    assert "totalBrokerFeeCashflow" in config
    assert "entryCommission=HistoryDealGetDouble(trans.deal,DEAL_COMMISSION)" in ea


def test_recovered_snapshots_and_netting_reversals_are_not_training_labels():
    tracker = TRACKER.read_text(encoding="utf-8")
    ea = EA.read_text(encoding="utf-8")
    assert "p.cashflowsKnown=false;p.outcomeHistoryComplete=false;" in tracker
    assert "if((!p.outcomeHistoryComplete||!p.cashflowsKnown)&&p.filled)coarseOutcome=\"ambiguous\";" in tracker
    compact_ea = "".join(ea.split())
    assert 'outcome="Ambiguous_NettingReversal";' in compact_ea
    assert "g_tracker.MarkHistoryIncomplete(decisionId);" in compact_ea



def test_restart_rebuilds_active_position_from_authoritative_deals_before_fallback():
    tracker = TRACKER.read_text(encoding="utf-8")
    recovery = (ROOT / "EA" / "includes" / "Recovery" / "RecoveryEngine.mqh").read_text(encoding="utf-8")
    assert "RebuildOpenDecisionFromHistory(TradeSetup &setup,long decisionId,ulong livePositionId,ulong magic)" in tracker
    assert "HistorySelect(fromTime,toTime)" in tracker
    assert "DEAL_POSITION_ID" in tracker
    assert "DEAL_ENTRY_OUT_BY" in tracker
    assert "MathAbs(expectedRemaining[i]-actualRemaining[i])>volumeTolerance" in tracker
    assert "DealAlreadyProcessed(dealTicket)" in tracker
    assert "m_tracker.RebuildOpenDecisionFromHistory(restoredDecision.setup,decisionId,positionIdentifier,m_magic)" in recovery
    assert "m_tracker.MarkHistoryIncomplete(decisionId);" in recovery


def test_history_rebuild_rejects_netting_reversals_and_missing_exposure_history():
    tracker = TRACKER.read_text(encoding="utf-8")
    assert "if(entry==DEAL_ENTRY_INOUT) return false;" in tracker
    assert "if(!liveEntryConfirmed || ArraySize(positionIds)==0) return false;" in tracker
    assert "MarkHistoryIncomplete(decisionId)" in tracker



def test_recovered_deal_ledger_does_not_fabricate_excursion_metrics():
    tracker = TRACKER.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    assert "bool cashflowsKnown; bool spreadCostKnown; bool slippageCostKnown; bool outcomeHistoryComplete; bool excursionHistoryComplete;" in config
    assert "state.excursionHistoryComplete=false;" in tracker
    assert "m_environmentMemory!=NULL&&p.excursionHistoryComplete" in tracker
    assert "if(!p.excursionHistoryComplete){mfeR=0.0;maeR=0.0;}" in tracker



def test_multi_fill_parent_accounting_uses_vwap_and_disables_excursion_training():
    tracker = TRACKER.read_text(encoding="utf-8")
    start = tracker.index("bool MarkExecuted(")
    end = tracker.index("bool RestoreExecuted(", start)
    executed = tracker[start:end]

    assert "double totalNotional=p.entryFillPrice*p.lots+fill*volume;" in executed
    assert "double totalLots=p.lots+volume;" in executed
    assert "p.entryFillPrice=averageFill;" in executed
    assert "p.entryRef=averageFill;" in executed
    assert "p.excursionHistoryComplete=false;" in executed
    assert "RememberDeal(dealTicket);" in executed


def test_non_finite_fill_and_exit_values_fail_closed_before_money_accounting():
    tracker = TRACKER.read_text(encoding="utf-8")
    entry_start = tracker.index("bool MarkExecuted(")
    entry_end = tracker.index("bool RestoreExecuted(", entry_start)
    entry = tracker[entry_start:entry_end]

    exit_start = tracker.index("bool MarkClosed(")
    exit_end = tracker.index("void Update(", exit_start)
    exit_body = tracker[exit_start:exit_end]

    assert "MathIsValidNumber(fill)" in entry
    assert "MathIsValidNumber(volume)" in entry
    assert entry.index("MathIsValidNumber(fill)") < entry.index("p.realizedPnL=nextPnL")
    assert "MarkHistoryIncomplete(id);" in entry
    assert "MathIsValidNumber(netPnl)" in exit_body
    assert "if(!pnlValid) netPnl=0.0;" in exit_body
    assert exit_body.index("MathIsValidNumber(netPnl)") < exit_body.index("p.realizedPnL=nextPnL")
    assert "p.outcomeHistoryComplete=false;" in exit_body
    assert "p.cashflowsKnown=false;" in exit_body



def test_partial_closes_reduce_remaining_volume_and_only_finalize_when_flat():
    tracker = TRACKER.read_text(encoding="utf-8")
    start = tracker.index("bool MarkClosed(")
    end = tracker.index("void Update(", start)
    closed = tracker[start:end]

    # Each broker deal is idempotent; a replay cannot charge P&L or volume twice.
    assert closed.index("if(DealAlreadyProcessed(dealTicket)) return true;") < closed.index("double nextPnL=")

    # Partial exits reduce the live remainder, while over-closes or missing
    # volume evidence make the history ineligible for calibration.
    assert "if(closedVolume>0.0)" in closed
    assert "closedVolume>p.remainingLots+1e-8" in closed
    assert "double left=p.remainingLots-closedVolume;" in closed
    assert "p.remainingLots=(MathIsValidNumber(left) ? MathMax(0.0,left) : 0.0);" in closed
    assert "if(!stillOpen && p.remainingLots>1e-8)" in closed
    assert "p.outcomeHistoryComplete=false;" in closed

    # A still-open position must retain its parent record. The final outcome
    # is emitted only after the caller reports that exposure is flat.
    assert closed.index("if(stillOpen) return true;") < closed.index("Finalize(i,outcome,exitPrice,t);")

    # Partial-exit cashflows are accumulated in the same net-P&L ledger and
    # signed cost telemetry remains separate for audit/reconciliation.
    assert "double nextPnL=p.realizedPnL+netPnl;" in closed
    assert "double nextCommissionCashflow=p.totalCommissionCashflow+commission;" in closed
    assert "double nextSwapCashflow=p.totalSwapCashflow+swap;" in closed
    assert "double nextFeeCashflow=p.totalBrokerFeeCashflow+fee;" in closed
