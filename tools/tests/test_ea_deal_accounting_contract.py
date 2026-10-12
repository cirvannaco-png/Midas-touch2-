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
    assert "p.realizedPnL+=commission+swap+fee;" in tracker
    assert "p.realizedPnL+=netPnl;" in tracker
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


def test_incremental_entry_fills_keep_authoritative_vwap_and_disable_inexact_excursions():
    tracker = TRACKER.read_text(encoding="utf-8")
    start = tracker.index("bool MarkExecuted(")
    end = tracker.index("bool RestoreExecuted(", start)
    method = tracker[start:end]

    # Invalid deal data must be rejected before it can mutate outcome accounting.
    assert "!MathIsValidNumber(fill)" in method
    assert "!MathIsValidNumber(volume)" in method
    assert "t<=0" in method

    # Each incremental fill contributes its actual price * volume and its own
    # stop exposure; the parent entry price is not left at the first fill.
    assert "p.entryFillPrice*p.lots+fill*volume" in method
    assert "p.entryFillPrice=nextEntryNotional/nextLots" in method
    assert "p.weightedRiskDistLots=nextRiskDistanceLots" in method
    assert "p.mgmtRiskDist=p.weightedRiskDistLots/p.lots" in method

    # Aggregate MFE/MAE does not prove slice-level excursions for later fills.
    assert "p.excursionHistoryComplete=false;" in method


def test_exit_deals_reject_nonfinite_pnl_costs_and_excess_close_volume():
    tracker = TRACKER.read_text(encoding="utf-8")
    start = tracker.index("bool MarkClosed(")
    end = tracker.index("void Update(", start)
    method = tracker[start:end]

    assert "!MathIsValidNumber(exitPrice)" in method
    assert "!MathIsValidNumber(netPnl)" in method
    assert "!MathIsValidNumber(commission)" in method
    assert "!MathIsValidNumber(swap)" in method
    assert "!MathIsValidNumber(fee)" in method
    assert "!MathIsValidNumber(closedVolume)" in method
    assert "closedVolume>p.remainingLots+" in method
    assert "MarkHistoryIncomplete(id);" in method
