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
    assert 'outcome="Ambiguous_NettingReversal";g_tracker.MarkHistoryIncomplete(decisionId);' in ea
