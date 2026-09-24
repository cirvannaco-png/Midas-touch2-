import pytest

from tools.research.counterfactual import compare_counterfactual_variants


def test_counterfactual_requires_exact_pairs():
    rows = [
        {"scenario_id": "a", "variant": "baseline", "realized_r": 1.0},
        {"scenario_id": "a", "variant": "candidate", "realized_r": 2.0},
        {"scenario_id": "b", "variant": "baseline", "realized_r": -1.0},
    ]
    with pytest.raises(ValueError, match="pairing incomplete"):
        compare_counterfactual_variants(
            rows, baseline_variant="baseline", alternative_variant="candidate"
        )


def test_counterfactual_reports_paired_delta():
    rows = [
        {"scenario_id": "a", "variant": "baseline", "realized_r": 1.0},
        {"scenario_id": "a", "variant": "candidate", "realized_r": 2.0},
        {"scenario_id": "b", "variant": "baseline", "realized_r": -1.0},
        {"scenario_id": "b", "variant": "candidate", "realized_r": 0.5},
    ]
    report = compare_counterfactual_variants(
        rows, baseline_variant="baseline", alternative_variant="candidate"
    )
    assert report.paired_scenarios == 2
    assert report.mean_delta_r == 1.25
    assert report.alternative_beats_baseline_fraction == 1.0
