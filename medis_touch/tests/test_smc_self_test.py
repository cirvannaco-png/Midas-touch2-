import pytest

from medis_touch.app.smc_self_test import (
    SMCCandidateResult,
    assert_frozen_configuration,
    evaluate_smc_stability,
    freeze_smc_configuration,
    smc_configuration_hash,
)


def _candidate(label: str, expectancy: float, *, degradation: float = 0.10) -> SMCCandidateResult:
    return SMCCandidateResult(
        parameters={"label": label, "fvg_max_dist_atr": 1.25},
        oos_windows=3,
        expectancy_r=expectancy,
        profit_factor=1.20,
        max_drawdown_r=2.0,
        win_rate=0.55,
        contribution_vs_baseline_r=0.10,
        contribution_vs_non_smc_r=0.08,
        oos_degradation=degradation,
    )


def test_smcs_stability_requires_a_plateau_not_a_single_optimum():
    report = evaluate_smc_stability([_candidate("best", 0.50), _candidate("near", 0.47)])
    assert report.passed is True
    assert report.neighbor_count == 1
    assert report.best_index == 0


def test_smcs_stability_rejects_razor_thin_optimum():
    report = evaluate_smc_stability([_candidate("best", 0.50), _candidate("weak", 0.20)])
    assert report.passed is False
    assert report.neighbor_count == 0


def test_smcs_stability_rejects_excessive_oos_degradation():
    report = evaluate_smc_stability(
        [_candidate("best", 0.50, degradation=0.40), _candidate("near", 0.48, degradation=0.10)]
    )
    assert report.passed is False


def test_smcs_freeze_requires_pass_and_hash_is_deterministic():
    candidate = _candidate("best", 0.50)
    report = evaluate_smc_stability([candidate, _candidate("near", 0.47)])
    frozen = freeze_smc_configuration(
        candidate,
        report,
        source_variant="midas_full",
        data_version="tester-2026-09-17",
    )
    assert frozen.config_hash == smc_configuration_hash(candidate.parameters)
    assert frozen.stability_report_passed is True
    assert_frozen_configuration(frozen, candidate.parameters)


def test_smcs_freeze_fails_closed_before_promotion():
    candidate = _candidate("best", 0.50)
    report = evaluate_smc_stability([candidate], required_neighbors=1)
    with pytest.raises(ValueError, match="before stability gate"):
        freeze_smc_configuration(
            candidate,
            report,
            source_variant="midas_full",
            data_version="tester-2026-09-17",
        )


def test_forward_test_fails_when_live_parameters_drift():
    candidate = _candidate("best", 0.50)
    report = evaluate_smc_stability([candidate, _candidate("near", 0.47)])
    frozen = freeze_smc_configuration(
        candidate,
        report,
        source_variant="midas_full",
        data_version="tester-2026-09-17",
    )
    with pytest.raises(ValueError, match="does not match frozen configuration"):
        assert_frozen_configuration(
            frozen,
            {"label": "best", "fvg_max_dist_atr": 1.30},
        )
