"""Static contract tests for inducement structural provenance telemetry.

These tests intentionally validate source-level wiring only. They do not infer
trading performance and do not promote any research candidate.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "EA" / "includes" / "Core" / "Config.mqh"
INDUCEMENT = ROOT / "EA" / "includes" / "SmartMoney" / "Inducement.mqh"
SCORING = ROOT / "EA" / "includes" / "Analysis" / "Scoring.mqh"
PUBLISHER = ROOT / "EA" / "includes" / "Signals" / "SignalPublisher.mqh"


def test_inducement_result_has_structural_provenance_fields():
    text = CONFIG.read_text(encoding="utf-8")
    required = [
        "ENUM_INDUCEMENT_STRUCTURE structureType",
        "double liquidityPoolPrice",
        "int liquidityPoolNearBarIndex",
        "int liquidityPoolFarBarIndex",
        "int liquidityPoolBarSpan",
        "double liquidityPoolSpacingATR",
        "double sweepPenetrationATR",
        "double sweepRejectionRatio",
        "double sweepShapeScore",
        "bool sweepFollowThrough",
        "int sweepFollowThroughBarIndex",
    ]
    for field in required:
        assert field in text


def test_inducement_populates_provenance_without_changing_gate_contract():
    text = INDUCEMENT.read_text(encoding="utf-8")
    # Keep the class declaration interface stable; validate the expanded telemetry
    # implementation separately so a research-only provenance change cannot drift
    # the public CInducement contract accidentally.
    assert "ENUM_SWEEP_GRADE  GradeSweep(int sweepBarIdx, bool forBuy, double poolPrice, double &gradeScore);" in text
    assert "ENUM_SWEEP_GRADE CInducement::GradeSweep(int sweepBarIdx, bool forBuy, double poolPrice, double &gradeScore, double &rejectionRatio, double &shapeScore, double &penetrationATR, bool &followThrough)" in text
    assert "r.structureType = structureFound ? INDUCEMENT_STRUCTURE_EQUAL_POOL : INDUCEMENT_STRUCTURE_NONE;" in text
    assert "r.sweepFollowThrough = followThrough;" in text
    assert "r.sweepPenetrationATR = penetrationATR;" in text
    assert "r.sweepRejectionRatio = rejectionRatio;" in text
    assert "r.sweepShapeScore = shapeScore;" in text
    assert "r.sweepFollowThroughBarIndex = (sweepBarIdx - 1 >= 0) ? sweepBarIdx - 1 : -1;" in text
    # Provenance must not silently become a live gate.
    assert "if(m_requireMinSweepGrade" in text
    assert "if(m_requireFreshSetup" in text


def test_scoring_copies_the_authoritative_inducement_result():
    text = SCORING.read_text(encoding="utf-8")
    required = [
        "out.inducement_structure_type = ind.structureType;",
        "out.liquidity_pool_price = ind.liquidityPoolPrice;",
        "out.liquidity_pool_near_bar_index = ind.liquidityPoolNearBarIndex;",
        "out.liquidity_pool_far_bar_index = ind.liquidityPoolFarBarIndex;",
        "out.liquidity_pool_bar_span = ind.liquidityPoolBarSpan;",
        "out.liquidity_pool_spacing_atr = ind.liquidityPoolSpacingATR;",
        "out.sweep_penetration_atr = ind.sweepPenetrationATR;",
        "out.sweep_rejection_ratio = ind.sweepRejectionRatio;",
        "out.sweep_shape_score = ind.sweepShapeScore;",
        "out.sweep_follow_through = ind.sweepFollowThrough;",
        "out.sweep_follow_through_bar_index = ind.sweepFollowThroughBarIndex;",
    ]
    for line in required:
        assert line in text


def test_signal_payload_exports_provenance_for_research_attribution():
    text = PUBLISHER.read_text(encoding="utf-8")
    required_json_keys = [
        '\\"inducement_structure_type\\":',
        '\\"liquidity_pool_price\\":',
        '\\"liquidity_pool_near_bar_index\\":',
        '\\"liquidity_pool_far_bar_index\\":',
        '\\"liquidity_pool_bar_span\\":',
        '\\"liquidity_pool_spacing_atr\\":',
        '\\"sweep_penetration_atr\\":',
        '\\"sweep_rejection_ratio\\":',
        '\\"sweep_shape_score\\":',
        '\\"sweep_follow_through\\":',
        '\\"sweep_follow_through_bar_index\\":',
    ]
    for key in required_json_keys:
        assert key in text


def test_scoring_exposes_the_winning_fvg_only_as_diagnostic_telemetry():
    text = SCORING.read_text(encoding="utf-8")
    assert "m_lastFvgState" in text
    assert "m_lastFvgAgeBars" in text
    assert "m_lastFvgDistanceATR" in text
    assert "m_lastFvgState = z.state;" in text
    assert "m_lastFvgAgeBars = MathMax(0, z.bar_index);" in text
    assert "m_lastFvgDistanceATR = distATR;" in text
    assert "out.best_fvg_state = m_lastFvgState;" in text
    assert "out.best_fvg_age_bars = m_lastFvgAgeBars;" in text
    assert "out.best_fvg_distance_atr = m_lastFvgDistanceATR;" in text


def test_signal_payload_exports_fvg_provenance():
    text = PUBLISHER.read_text(encoding="utf-8")
    for key in [
        '\\"best_fvg_state\\":',
        '\\"best_fvg_age_bars\\":',
        '\\"best_fvg_distance_atr\\":',
    ]:
        assert key in text
