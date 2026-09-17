from dataclasses import dataclass

from tools.context_ablation import context_effects, observed_slices


@dataclass
class Row:
    signal_id: str
    outcome: str
    realized_r: float
    environment: dict


def test_context_slices_require_minimum_sample_before_expectancy_is_reported():
    rows = [Row(str(i), "win" if i % 2 else "loss", 1.0 if i % 2 else -1.0,
                 {"htf_ob_aligned": True, "value_area_zone": "VA_ZONE_INSIDE"}) for i in range(30)]
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


def test_context_effects_cover_requested_environment_features():
    rows = []
    for i in range(60):
        positive = i % 2 == 0
        rows.append(Row(str(i), "win" if positive else "loss", 1.0 if positive else -1.0, {
            "htf_ob_aligned": i < 30,
            "value_area_zone": "VA_ZONE_INSIDE" if i < 30 else "VA_ZONE_UNDEFINED",
            "liquidity_score": 1.0 if i < 30 else 0.0,
            "market_structure": "BOS" if i < 30 else "",
            "volatility_state": "VOL_REGIME_NORMAL" if i < 30 else "VOL_REGIME_UNDEFINED",
            "news_state": "NEWS_NONE" if i < 30 else "NEWS_WARNING",
        }))
    effects = context_effects(rows, min_sample=30)
    assert set(effects) == {"htf_order_block", "value_area", "liquidity", "market_structure", "volatility", "news_clear"}
    assert all(effect.enough_data for effect in effects.values())
