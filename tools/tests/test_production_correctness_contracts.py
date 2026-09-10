from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA"


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_outcome_tracker_has_closed_bar_gate_and_actual_fill_reporting():
    src = text("EA/includes/Trading/OutcomeTracker.mqh")
    assert "GetCandle(1)" in src
    assert "m_lastProcessedBarTime" in src
    assert "fillPrice = m_pending[i].filled ? m_pending[i].entryFillPrice : 0.0" in src
    assert "m_pending[idx] = p; return;" in src


def test_ea_updates_outcomes_before_new_entry_gates():
    src = text("EA/MedisTouch_v2.8.mq5")
    update = src.index("if(isNewBar && InpTrackOutcomes) g_tracker.Update(g_chartCtx);")
    hard = src.index("g_riskGuard.IsHardHalted", update)
    daily = src.index("g_riskGuard.IsDailyLossLimitHit", hard)
    assert update < hard < daily
    assert "if(!isNewBar)return;" in src


def test_risk_guard_is_account_scoped_and_persistent():
    src = text("EA/includes/Portfolio/RiskGuard.mqh")
    assert "ACCOUNT_LOGIN" in src
    assert "ACCOUNT_SERVER" in src
    assert "magicNumber" in src
    assert "m_gvDayIdKey" in src
    assert "m_gvDayEquityKey" in src


def test_decision_store_persists_before_memory_mutation():
    src = text("EA/includes/Decision/DecisionStore.mqh")
    save = src.index("bool CDecisionStore::Save(")
    append = src.index("if(!AppendLine(m_decisionsFile", save)
    memory = src.index("ArrayResize(m_decisions", append)
    assert append < memory


def test_volume_is_normalized_after_step_rounding():
    src = text("EA/includes/Trading/RiskEngine.mqh")
    assert "NormalizeDouble(lots,precision)" in src


def test_targets_and_trade_zone_use_execution_edge():
    zone = text("EA/includes/Trading/TradeZone.mqh")
    assert "AssignTargets(setup,m_liqCtx,m_priceRef.Symbol(),atr,setup.entry_top)" in zone
    assert "AssignTargets(setup,m_liqCtx,m_priceRef.Symbol(),atr,setup.entry_bottom)" in zone
