from dataclasses import dataclass

from tools.context_ablation import observed_slices


@dataclass
class Row:
    signal_id: str
    outcome: str
    realized_r: float
    environment: dict


def test_context_slices_require_minimum_sample_before_expectancy_is_reported():
    rows = [
        Row(str(i), "win" if i % 2 else "loss", 1.0 if i % 2 else -1.0,
            {"htf_ob_aligned": True, "value_area_zone": "VA_ZONE_INSIDE"})
        for i in range(30)
    ]
    result = observed_slices(rows, min_sample=30)
    assert result["base"].n == 30
    assert result["base_plus_htf_ob"].n == 30
    assert result["base_plus_value_area"].n == 30
    assert result["base_plus_both"].n == 30
    assert result["base"].expectancy_r == 0.0


def test_context_slices_do_not_claim_results_from_tiny_samples():
    rows = [Row(str(i), "win", 1.0, {"htf_ob_aligned": True}) for i in range(5)]
    result = observed_slices(rows, min_sample=30)
    assert result["base_plus_htf_ob"].n == 5
    assert result["base_plus_htf_ob"].expectancy_r is None
