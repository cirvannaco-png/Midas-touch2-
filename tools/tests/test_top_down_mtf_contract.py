from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_top_down_layer_uses_all_seven_timeframes_and_weighted_context() -> None:
    source = (ROOT / "EA/includes/Analysis/TopDownMTFEngine.mqh").read_text(encoding="utf-8")
    for name in ("m_d1", "m_h4", "m_h1", "m_m30", "m_m15", "m_m5", "m_m1"):
        assert name in source
    for weight in ("30.0", "24.0", "18.0", "10.0", "8.0", "6.0", "4.0"):
        assert weight in source
    assert "m_longScore-m_shortScore" in source
    assert "m_maxConfidenceAdjustment*directionalEdge/100.0" in source


def test_mtf_adjustment_is_opt_in_bounded_and_both_sides_are_adjusted_independently() -> None:
    ea = (ROOT / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    source = (ROOT / "EA/includes/Analysis/TopDownMTFEngine.mqh").read_text(encoding="utf-8")
    assert "InpEnableTopDownMTF=false" in ea
    assert "g_topDownMTF.AdjustSetup(buySetup)" in ea
    assert "g_topDownMTF.AdjustSetup(sellSetup)" in ea
    assert "MathMin(15.0,maxConfidenceAdjustment)" in source
    assert "MathMax(0.0,MathMin(100.0,value))" in source
    assert "does not hard-block every countertrend setup" in ea


def test_equal_buy_sell_candidates_are_not_biased_toward_buy() -> None:
    ea = (ROOT / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    assert 'delta>InpMinDirectionalAdvantage' in ea
    assert '-delta>InpMinDirectionalAdvantage' in ea
    assert 'DIRECTIONAL_CONFLICT' in ea


def test_top_down_stack_fails_closed_when_enabled_but_data_is_missing() -> None:
    ea = (ROOT / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    source = (ROOT / "EA/includes/Analysis/TopDownMTFEngine.mqh").read_text(encoding="utf-8")
    assert "if(!g_topDownMTF.Evaluate())" in ea
    assert "MTF_CONTEXT_UNAVAILABLE" in ea
    assert "InpEnableTopDownMTF && _Period!=PERIOD_M1" in ea
    assert "INIT_PARAMETERS_INCORRECT" in ea
    assert 'm_summary="top-down context unavailable' in source
    assert "m_ready=false;" in source


def test_timeframe_pool_never_aliases_the_wrong_timeframe_when_full() -> None:
    source = (ROOT / "EA/includes/Analysis/TFContext.mqh").read_text(encoding="utf-8")
    assert "#define TFPOOL_MAX 16" in source
    full_block = source[source.index("if(m_count >= TFPOOL_MAX)"):source.index("CTFContext* c = new CTFContext();")]
    assert "return NULL;" in full_block
    assert "return m_ctx[m_count - 1]" not in full_block


def test_drawdown_controller_only_de_risks_at_daily_loss_tiers() -> None:
    source = (ROOT / "EA/includes/Portfolio/RiskGuard.mqh").read_text(encoding="utf-8")
    start = source.index("double CRiskGuard::SizeMultiplier()")
    end = source.index("string CRiskGuard::RiskStateName()", start)
    policy = source[start:end]
    assert "dailyRatio>=0.75" in policy and "MathMin(multiplier,0.25)" in policy
    assert "dailyRatio>=0.50" in policy and "MathMin(multiplier,0.50)" in policy
    assert "dailyRatio>=0.25" in policy and "MathMin(multiplier,0.75)" in policy
    assert "if(dailyLoss>=m_maxDailyLossPercent) return 0.0;" in policy
    assert "MathMax(0.0,MathMin(1.0,multiplier))" in policy
    assert "RiskStateName()" in source


def test_risk_multiplier_remains_in_actual_automated_order_sizing_path() -> None:
    ea = (ROOT / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")
    assert "g_riskGuard.SizeMultiplier()" in ea
    assert "InpEnableTopDownMTF=false" in ea
    assert "InpEnableProgressiveDailyLossDeRisk=false" in ea
    assert "InpEnableProgressiveDailyLossDeRisk);" in ea
    docs = (ROOT / "docs/MT2_TOP_DOWN_MTF_VALIDATION.md").read_text(encoding="utf-8")
    assert "genuine MT5 Strategy Tester results" in docs
    assert "not proof that the strategy is profitable" in docs
