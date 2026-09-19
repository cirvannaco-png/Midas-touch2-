from medis_touch.app.adaptive_research import (
    ResearchObservation,
    architecture_ablation,
    context_ablation,
    smc_forward_test_gate,
    summarize,
    walk_forward_research,
)
from medis_touch.app.smc_self_test import SMCCandidateResult


def _rows(n=10):
    return [
        ResearchObservation(
            timestamp=i,
            strategy="SMC" if i % 2 == 0 else "MOMENTUM_BREAKOUT",
            realized_r=1.0 if i % 3 else -1.0,
            environment={"regime": "TRENDING"},
            htf_ob=(i % 2 == 0),
            value_area=(i % 3 == 0),
            smc=(i % 2 == 0),
        )
        for i in range(n)
    ]


def _candidate(label: str, expectancy: float) -> SMCCandidateResult:
    return SMCCandidateResult(
        parameters={"label": label, "fvg_max_dist_atr": 1.25},
        oos_windows=3,
        expectancy_r=expectancy,
        profit_factor=1.20,
        max_drawdown_r=2.0,
        win_rate=0.55,
        contribution_vs_baseline_r=0.10,
        contribution_vs_non_smc_r=0.08,
        oos_degradation=0.10,
    )


def test_summary_exposes_required_core_metrics():
    result = summarize(_rows())
    assert result.n == 10
    assert 0.0 <= result.win_rate <= 1.0
    assert result.expectancy_r == result.average_r
    assert result.max_drawdown_r >= 0.0


def test_context_ablation_has_requested_slices():
    result = context_ablation(_rows())
    assert set(result) == {
        "base",
        "base_plus_htf_ob",
        "base_plus_value_area",
        "base_plus_both",
    }


def test_architecture_ablation_has_requested_views():
    result = architecture_ablation(_rows())
    assert set(result) == {
        "midas_full",
        "midas_without_smc",
        "smc_only",
        "regime_plus_non_smc",
    }


def test_walk_forward_never_trains_on_validation_rows():
    rows = _rows(12)
    seen = []

    def learner(train):
        seen.append((train[0].timestamp, train[-1].timestamp))
        return train[-1].timestamp

    def evaluator(model, test):
        assert model < test[0].timestamp
        return summarize(test)

    results = walk_forward_research(rows, train_size=6, test_size=3, learner=learner, evaluator=evaluator)
    assert results
    assert seen == [(0, 5), (3, 8)]


def test_smc_forward_test_gate_requires_stable_winner_and_freezes_identity():
    candidates = [_candidate("best", 0.50), _candidate("near", 0.47)]
    report, frozen = smc_forward_test_gate(
        candidates,
        selected_candidate_index=0,
        source_variant="midas_full",
        data_version="tester-2026-09-17",
    )
    assert report.passed is True
    assert frozen.parameters == candidates[0].parameters
    assert frozen.stability_report_passed is True


def test_smc_forward_test_gate_rejects_non_winner_selection():
    candidates = [_candidate("best", 0.50), _candidate("near", 0.47)]
    try:
        smc_forward_test_gate(
            candidates,
            selected_candidate_index=1,
            source_variant="midas_full",
            data_version="tester-2026-09-17",
        )
    except ValueError as exc:
        assert "stability winner" in str(exc)
    else:
        raise AssertionError("expected non-winner selection to fail closed")
