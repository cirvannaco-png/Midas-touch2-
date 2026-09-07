from optimizer import ParameterBound, SearchBudget, bounded_delta, propose_neighbors


def test_proposals_are_bounded_deterministic_and_include_baseline():
    baseline = {"confidence": 0.90, "fvg": 0.20}
    bounds = {
        "confidence": ParameterBound(0.80, 0.95, 0.05),
        "fvg": ParameterBound(0.10, 0.30, 0.10),
    }

    first = propose_neighbors(baseline, bounds, radius=1, budget=SearchBudget(20))
    second = propose_neighbors(baseline, bounds, radius=1, budget=SearchBudget(20))

    assert first == second
    assert baseline in first
    assert all(
        bounds[k].minimum <= candidate[k] <= bounds[k].maximum
        for candidate in first
        for k in bounds
    )


def test_search_budget_caps_cartesian_generation():
    baseline = {"a": 5.0, "b": 5.0, "c": 5.0}
    bounds = {key: ParameterBound(0.0, 10.0, 1.0) for key in baseline}

    candidates = propose_neighbors(
        baseline, bounds, radius=2, budget=SearchBudget(max_candidates=7)
    )

    assert len(candidates) == 7


def test_bounded_delta_fails_closed_outside_declared_range():
    baseline = {"confidence": 0.90}
    bounds = {"confidence": ParameterBound(0.80, 0.95, 0.05)}

    assert bounded_delta(baseline, {"confidence": -0.05}, bounds) == {"confidence": 0.85}

    try:
        bounded_delta(baseline, {"confidence": 0.10}, bounds)
    except ValueError as exc:
        assert "exceeds declared bounds" in str(exc)
    else:
        raise AssertionError("out-of-bounds proposal must fail closed")
