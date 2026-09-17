from medis_touch.app.adaptive_research import ResearchObservation, architecture_ablation, context_ablation, summarize, walk_forward_research


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


def test_summary_exposes_required_core_metrics():
    result = summarize(_rows())
    assert result.n == 10
    assert 0.0 <= result.win_rate <= 1.0
    assert result.expectancy_r == result.average_r
    assert result.max_drawdown_r >= 0.0


def test_context_ablation_has_requested_slices():
    result = context_ablation(_rows())
    assert set(result) == {"base", "base_plus_htf_ob", "base_plus_value_area", "base_plus_both"}


def test_architecture_ablation_has_requested_views():
    result = architecture_ablation(_rows())
    assert set(result) == {"midas_full", "midas_without_smc", "smc_only", "regime_plus_non_smc"}


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
