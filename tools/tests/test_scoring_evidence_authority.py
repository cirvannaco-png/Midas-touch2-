from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_entry_timeframe_structure_evidence_is_counted_once():
    source = (ROOT / "EA" / "includes" / "Analysis" / "Scoring.mqh").read_text(
        encoding="utf-8"
    )
    assert "Inducement is the sole authoritative entry-timeframe source" in source

    start = source.index("double CScoringEngine::CalculateConfidence(bool forBuy)")
    end = source.index("double CScoringEngine::PipSize()", start)
    body = source[start:end]

    # BOS/liquidity/sweep/structure evidence is already represented by the
    # authoritative inducement total; only independent feature families add
    # separate ranking points here.
    assert "double score = ind.totalScore;" in body
    assert "score += 15.0 * FVGScore(forBuy);" in body
    assert "score += 15.0 * TrendScore(forBuy);" in body
    assert "score += 5.0 * VolumeScore(forBuy);" in body
    assert "score += 5.0 * FibonacciScore(forBuy);" in body
    assert "score += 5.0 * ValueAreaScore(forBuy);" in body
    assert "score += 5.0 * OBScore(forBuy);" in body
    assert "BOSScore(" not in body
    assert "LiquidityScore(" not in body
    assert "const double MAX_RAW_SCORE = 120.0;" in body
