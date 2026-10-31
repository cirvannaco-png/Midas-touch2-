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



def test_candidate_selection_receives_only_strictly_chronological_development_partitions():
    from datetime import datetime, timedelta, timezone

    from oos_firewall import TemporalSplit
    from optimizer import candidate_selection_development_partitions

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    train = [
        {"partition": "train", "signal_time": start.isoformat(), "id": "train-1"},
        {"partition": "train", "signal_time": (start + timedelta(days=1)).isoformat(), "id": "train-2"},
    ]
    validation = [
        {"partition": "validation", "signal_time": (start + timedelta(days=3)).isoformat(), "id": "validation-1"},
    ]
    locked_oos = [
        {"partition": "locked_oos", "signal_time": (start + timedelta(days=5)).isoformat(), "id": "oos-1"},
    ]

    optimizer_train, optimizer_validation = candidate_selection_development_partitions(
        TemporalSplit(train, validation, locked_oos)
    )
    assert [row["id"] for row in optimizer_train] == ["train-1", "train-2"]
    assert [row["id"] for row in optimizer_validation] == ["validation-1"]
    assert all(row["partition"] != "locked_oos" for row in optimizer_train + optimizer_validation)


def test_candidate_selection_rejects_locked_oos_rows_smuggled_into_train_or_validation():
    from datetime import datetime, timedelta, timezone

    import pytest

    from oos_firewall import OOSPurityError, TemporalSplit
    from optimizer import candidate_selection_development_partitions

    start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    train = [{"partition": "train", "signal_time": start.isoformat(), "id": "train"}]
    validation = [
        {"partition": "validation", "signal_time": (start + timedelta(days=2)).isoformat(), "id": "validation"},
        {"partition": "locked_oos", "signal_time": (start + timedelta(days=4)).isoformat(), "id": "smuggled-oos"},
    ]
    locked_oos = [
        {"partition": "locked_oos", "signal_time": (start + timedelta(days=6)).isoformat(), "id": "locked-oos"},
    ]

    with pytest.raises(OOSPurityError, match="different or missing partition label"):
        candidate_selection_development_partitions(TemporalSplit(train, validation, locked_oos))


def test_candidate_selection_rejects_time_overlap_even_when_roles_are_correct():
    from datetime import datetime, timedelta, timezone

    import pytest

    from oos_firewall import OOSPurityError, TemporalSplit
    from optimizer import candidate_selection_development_partitions

    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    train = [{"partition": "train", "signal_time": start.isoformat(), "id": "train"}]
    validation = [{"partition": "validation", "signal_time": (start + timedelta(days=2)).isoformat(), "id": "validation"}]
    locked_oos = [{"partition": "locked_oos", "signal_time": (start + timedelta(days=2)).isoformat(), "id": "oos"}]

    with pytest.raises(OOSPurityError, match="validation_max_signal_time"):
        candidate_selection_development_partitions(TemporalSplit(train, validation, locked_oos))
