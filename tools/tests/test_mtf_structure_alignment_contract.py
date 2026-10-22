from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCORING = (ROOT / "EA/includes/Analysis/Scoring.mqh").read_text(encoding="utf-8")
EA = (ROOT / "EA/MedisTouch_v2.8.mq5").read_text(encoding="utf-8")


def _function_body(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_mtf_alignment_is_research_only_and_freshness_is_configurable() -> None:
    assert "input bool InpRequireMtfStructureAlignment=false" in EA
    assert "input int InpMtfMaxBosAgeBars=20" in EA
    assert "ConfigureMTFStructureAlignment(InpRequireMtfStructureAlignment,InpMtfMaxBosAgeBars)" in EA
    assert "m_requireMtfStructureAlignment(false), m_mtfMaxBosAgeBars(20)" in SCORING
    assert "if(m_mtfMaxBosAgeBars < 1) m_mtfMaxBosAgeBars = 1;" in SCORING
    assert "if(m_mtfMaxBosAgeBars > 500) m_mtfMaxBosAgeBars = 500;" in SCORING


def test_mtf_context_requires_confirmed_directional_fresh_bos_with_lineage() -> None:
    body = _function_body(
        SCORING,
        "bool CScoringEngine::ContextMTFStructureAligned",
        "bool CScoringEngine::MTFStructureAligned",
    )
    assert "ctx.bos.Count() <= 0" in body
    assert "latestBOS.is_bullish != forBuy" in body
    assert "latestBOS.bar_index < 1" in body
    assert "bosCandle.time != latestBOS.time" in body
    assert "int barsSinceBOS = latestBOS.bar_index - 1;" in body
    assert "barsSinceBOS > m_mtfMaxBosAgeBars" in body


def test_newer_opposing_choch_blocks_but_older_choch_does_not_override_bos() -> None:
    body = _function_body(
        SCORING,
        "bool CScoringEngine::ContextMTFStructureAligned",
        "bool CScoringEngine::MTFStructureAligned",
    )
    assert "latestCHOCH.time > latestBOS.time" in body
    assert "latestCHOCH.bullish != forBuy" in body


def test_same_timeframe_is_one_evidence_source_and_distinct_timeframes_must_both_pass() -> None:
    body = _function_body(
        SCORING,
        "bool CScoringEngine::MTFStructureAligned",
        "double CScoringEngine::TrendScore",
    )
    assert "if(m_trendCtx.tf == m_bosCtx.tf)" in body
    assert body.count("return ContextMTFStructureAligned(m_trendCtx, forBuy);") == 1
    assert (
        "return ContextMTFStructureAligned(m_trendCtx, forBuy)"
        "\n          && ContextMTFStructureAligned(m_bosCtx, forBuy);"
    ) in body


def test_research_gate_is_not_applied_when_disabled() -> None:
    body = _function_body(
        SCORING,
        "double CScoringEngine::CalculateConfidence(bool forBuy)",
        "double CScoringEngine::PipSize()",
    )
    assert "if(m_requireMtfStructureAlignment && !MTFStructureAligned(forBuy))" in body
    assert "if(!ind.valid) return 0.0;" in body


def test_mtf_alignment_fails_closed_for_missing_context_and_wrong_trend() -> None:
    body = _function_body(
        SCORING,
        "bool CScoringEngine::ContextMTFStructureAligned",
        "bool CScoringEngine::MTFStructureAligned",
    )
    assert "if(ctx == NULL || !ctx.candles.IsReady() || ctx.candles.Total() < 2)" in body
    assert "if(!trendAligned || ctx.bos.Count() <= 0)" in body


def test_mtf_alignment_rejects_future_or_forming_bar_events() -> None:
    body = _function_body(
        SCORING,
        "bool CScoringEngine::ContextMTFStructureAligned",
        "bool CScoringEngine::MTFStructureAligned",
    )
    assert "CandleData latestClosed = ctx.candles.GetCandle(1);" in body
    assert "latestBOS.time > latestClosed.time" in body
    assert "if(latestCHOCH.time > latestClosed.time)" in body


def test_opposing_choch_is_only_authoritative_when_newer_than_latest_bos() -> None:
    body = _function_body(
        SCORING,
        "bool CScoringEngine::ContextMTFStructureAligned",
        "bool CScoringEngine::MTFStructureAligned",
    )
    assert "if(latestCHOCH.time > latestBOS.time && latestCHOCH.bullish != forBuy)" in body
