import math

import pytest

from tools.multiple_testing import holm_bonferroni
from tools.paired_stats import paired_mean_test


def test_holm_bonferroni_preserves_input_order_and_controls_familywise_error():
    result = holm_bonferroni([0.01, 0.04, 0.03], alpha=0.05)
    assert [row.index for row in result] == [0, 1, 2]
    assert [row.adjusted_p for row in result] == pytest.approx([0.03, 0.06, 0.06])
    assert [row.reject for row in result] == [True, False, False]


def test_holm_bonferroni_handles_empty_and_boundary_values():
    assert holm_bonferroni([]) == []
    result = holm_bonferroni([0.0, 1.0], alpha=0.05)
    assert [row.adjusted_p for row in result] == [0.0, 1.0]
    assert [row.reject for row in result] == [True, False]


@pytest.mark.parametrize(
    "p_values,alpha",
    [
        ([float("nan")], 0.05),
        ([float("inf")], 0.05),
        ([-0.1], 0.05),
        ([1.1], 0.05),
        ([0.01], float("nan")),
        ([0.01], 1.0),
    ],
)
def test_holm_bonferroni_rejects_invalid_probability_inputs(p_values, alpha):
    with pytest.raises(ValueError):
        holm_bonferroni(p_values, alpha=alpha)


def test_paired_mean_test_requires_aligned_opportunities():
    with pytest.raises(ValueError, match="equal length"):
        paired_mean_test([1.0, 2.0], [1.0])


def test_paired_mean_test_reports_positive_consistent_improvement():
    result = paired_mean_test([1.0, 2.0, 3.0, 4.0], [2.0, 3.0, 4.0, 5.0])
    assert result.n == 4
    assert result.mean_delta == pytest.approx(1.0)
    assert result.standard_error == 0.0
    # A zero-variance sample cannot estimate the sampling distribution.
    # Preserve the infinite ratio convention but fail closed on significance.
    assert math.isinf(result.t_statistic)
    assert result.p_value == 1.0
    assert result.significant is False


def test_paired_mean_test_does_not_call_a_non_improvement_significant():
    result = paired_mean_test([2.0, 3.0, 4.0], [1.0, 2.0, 3.0])
    assert result.mean_delta == pytest.approx(-1.0)
    assert result.significant is False


@pytest.mark.parametrize(
    "baseline,candidate",
    [
        ([1.0], [1.0]),
        ([1.0, float("nan")], [2.0, 3.0]),
        ([1.0, 2.0], [2.0, float("inf")]),
    ],
)
def test_paired_mean_test_rejects_insufficient_or_non_finite_data(baseline, candidate):
    with pytest.raises(ValueError):
        paired_mean_test(baseline, candidate)
