from tools.champion_challenger import CandidateEvidence, qualify


def test_candidate_requires_locked_oos_and_sample():
    result = qualify(CandidateEvidence("x", 50, 1.2, 2.0, 0.5, 0.7, True, True, False))
    assert not result.eligible
    assert "OOS_NOT_LOCKED" in result.reasons
    assert "INSUFFICIENT_SAMPLE" in result.reasons


def test_candidate_can_be_eligible_with_all_evidence():
    result = qualify(CandidateEvidence("x", 120, 1.2, 2.0, 0.5, 0.7, True, True, True))
    assert result.eligible
