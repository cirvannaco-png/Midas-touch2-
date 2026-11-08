import math

import pytest

from tools.paired_stats import paired_mean_test


def test_small_sample_uses_student_t_tail_not_normal_approximation():
    # Paired deltas are [1, 2], so t=3 with one degree of freedom.
    result = paired_mean_test([0.0, 0.0], [1.0, 2.0])
    assert result.n == 2
    assert result.t_statistic == pytest.approx(3.0)
    assert result.p_value == pytest.approx(0.20483276469913345, rel=1e-10)
    assert not result.significant


def test_large_sample_p_value_is_bounded_and_significance_requires_improvement():
    baseline = [float(i) for i in range(40)]
    candidate = [value + (1.0 if i % 2 else 1.2) for i, value in enumerate(baseline)]
    result = paired_mean_test(baseline, candidate)
    assert 0.0 <= result.p_value <= 1.0
    assert result.mean_delta > 0.0
    assert result.significant


def test_constant_paired_delta_does_not_claim_statistical_certainty():
    result = paired_mean_test([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])
    assert result.standard_error == 0.0
    assert result.p_value == 1.0
    assert not result.significant


def test_paired_test_rejects_mismatched_or_non_finite_samples():
    with pytest.raises(ValueError, match="equal length"):
        paired_mean_test([1.0, 2.0], [2.0])
    with pytest.raises(ValueError, match="finite"):
        paired_mean_test([1.0, math.inf], [2.0, 3.0])


def test_paired_test_rejects_invalid_alpha_and_too_few_pairs():
    with pytest.raises(ValueError, match="alpha"):
        paired_mean_test([1.0, 2.0], [2.0, 3.0], alpha=1.0)
    with pytest.raises(ValueError, match="at least two"):
        paired_mean_test([1.0], [2.0])
