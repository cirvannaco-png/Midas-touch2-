import pytest
from medis_touch.app.model_monitoring import (
    brier_score,
    calibration_error,
    drift_state,
    expected_calibration_error,
    jensen_shannon_divergence,
    population_stability_index,
)


def test_psi_is_zero_for_identical_samples():
    values = [0.1, 0.2, 0.3, 0.4]
    assert population_stability_index(values, values) == pytest.approx(0.0)


def test_drift_state_escalates_with_psi():
    assert drift_state(0.05) == "NORMAL"
    assert drift_state(0.15) == "WATCH"
    assert drift_state(0.30) == "RESTRICT"


def test_jsd_is_symmetric_and_zero_for_identical_distributions():
    p = [0.2, 0.8]
    q = [0.7, 0.3]
    assert jensen_shannon_divergence(p, p) == pytest.approx(0.0)
    assert jensen_shannon_divergence(p, q) == pytest.approx(jensen_shannon_divergence(q, p))


def test_calibration_metrics_are_explicit():
    assert calibration_error([0.9, 0.1], [1, 0]) == pytest.approx(0.1)
    assert expected_calibration_error([0.9, 0.1], [1, 0], bins=2) == pytest.approx(0.1)
    assert brier_score([0.9, 0.1], [1, 0]) == pytest.approx(0.01)


def test_invalid_distribution_rejected():
    with pytest.raises(ValueError):
        jensen_shannon_divergence([0.5, 0.4], [0.5, 0.5])


def test_invalid_drift_thresholds_rejected():
    with pytest.raises(ValueError):
        drift_state(0.1, watch=0.3, restrict=0.2)
