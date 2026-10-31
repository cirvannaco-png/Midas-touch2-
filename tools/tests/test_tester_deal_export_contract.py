"""Contract checks for native Strategy Tester deal evidence export."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_deal_export_is_hard_disabled_outside_strategy_tester():
    ea = read("EA/MedisTouch_v2.8.mq5")
    exporter = read("EA/includes/Execution/TesterDealExport.mqh")

    assert "input string InpTesterExportRunId=" in ea
    assert "g_testerDealExport.Init(InpTesterExportRunId,_Symbol,InpMagicNumber," in ea
    assert "m_enabled=(enabled && (bool)MQLInfoInteger(MQL_TESTER));" in exporter
    assert "g_testerDealExport.Finalize();" in ea


def test_export_retains_costs_and_position_level_risk_basis():
    ea = read("EA/MedisTouch_v2.8.mq5")
    exporter = read("EA/includes/Execution/TesterDealExport.mqh")

    assert "HistoryDealGetDouble(trans.deal,DEAL_PROFIT)" in ea
    assert "HistoryDealGetDouble(trans.deal,DEAL_COMMISSION)" in ea
    assert "HistoryDealGetDouble(trans.deal,DEAL_SWAP)" in ea
    assert "HistoryDealGetDouble(trans.deal,DEAL_FEE)" in ea
    assert "entryRiskCash=g_risk.RiskAmountForLots" in ea
    assert 'FileWrite(handle,"position_id","time","entry","volume","profit","commission"' in exporter
    assert 'DoubleToString(RiskCash(row.position_id),8)' in exporter
    assert re_search_lane_ea(exporter)


def re_search_lane_ea(exporter: str) -> bool:
    return '                    "EA",' in exporter


def test_export_observes_spread_and_preserves_unique_run_identity():
    ea = read("EA/MedisTouch_v2.8.mq5")
    exporter = read("EA/includes/Execution/TesterDealExport.mqh")

    assert "g_testerDealExport.ObserveSpread(_Symbol);" in ea
    assert 'm_runId=SafeName(runId+"_"+IntegerToString((long)GetTickCount()));' in exporter
    assert "spread_points_mean" in exporter
    assert "spread_points_max" in exporter

    
def test_export_marks_raw_deal_timestamps_as_broker_server_local_not_utc():
    exporter = read("EA/includes/Execution/TesterDealExport.mqh")

    assert "string TimeServerLocal(datetime value) const" in exporter
    assert "timestamp_basis" in exporter
    assert "broker_server_local" in exporter
    assert "TimeServerLocal(row.deal_time)" in exporter
    assert 'return stamp+"Z";' not in exporter
    assert "Exness" not in exporter
