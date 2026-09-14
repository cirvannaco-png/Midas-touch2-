"""Tests for statistically gated recalibration decisions."""
from gating import GatingError, _validate_cycles, decide
from stats import wilson_ci

WV = "v2.11-candidate"


def _cycle(cycle_id, source, win_rate_stat, generated_at="2026-01-01T00:00:00+00:00"):
    return {
        "cycle_id": cycle_id,
        "source": source,
        "generated_at": generated_at,
        "expectancy": {"by_weight_version_stats": {WV: {"win_rate": win_rate_stat.to_dict()}}},
    }


def test_validate_cycles_rejects_empty_history():
    try:
        _validate_cycles([], WV)
        assert False, "expected GatingError"
    except GatingError as e:
        assert "empty" in str(e).lower()


def test_validate_cycles_rejects_mixed_sources():
    cycles = [_cycle("c0", "live", wilson_ci(50, 100)), _cycle("c1", "synthetic", wilson_ci(50, 100))]
    try:
        _validate_cycles(cycles, WV)
        assert False, "expected GatingError"
    except GatingError as e:
        assert "mixes synthetic and live" in str(e)


def test_validate_cycles_rejects_missing_tags():
    cycles = [{"expectancy": {}}]
    try:
        _validate_cycles(cycles, WV)
        assert False, "expected GatingError"
    except GatingError as e:
        assert "must carry" in str(e)


def test_validate_cycles_accepts_pure_live_history():
    cycles = [_cycle("c0", "live", wilson_ci(50, 100)), _cycle("c1", "live", wilson_ci(52, 100))]
    _validate_cycles(cycles, WV)


def test_decide_insufficient_data_below_persistence_threshold():
    cycles = [_cycle("c0", "live", wilson_ci(50, 100)), _cycle("c1", "live", wilson_ci(55, 100))]
    d = decide(cycles, WV)
    assert d.action == "INSUFFICIENT_DATA"
    assert d.cycles_considered == 2


def test_decide_holds_when_cis_overlap_throughout():
    cycles = [
        _cycle("c0", "live", wilson_ci(48, 100)),
        _cycle("c1", "live", wilson_ci(50, 100)),
        _cycle("c2", "live", wilson_ci(52, 100)),
    ]
    d = decide(cycles, WV)
    assert d.action == "HOLD"


def test_decide_promotes_on_persistent_improvement():
    cycles = [
        _cycle("c0", "live", wilson_ci(20, 100)),
        _cycle("c1", "live", wilson_ci(50, 100)),
        _cycle("c2", "live", wilson_ci(85, 100)),
    ]
    d = decide(cycles, WV)
    assert d.action == "HOLD"
    assert d.cycles_considered == 3


def test_decide_rolls_back_on_persistent_regression():
    cycles = [
        _cycle("c0", "live", wilson_ci(85, 100)),
        _cycle("c1", "live", wilson_ci(50, 100)),
        _cycle("c2", "live", wilson_ci(20, 100)),
    ]
    d = decide(cycles, WV)
    assert d.action == "HOLD"


def test_decide_rolls_back_on_contradiction_not_average():
    cycles = [
        _cycle("c0", "live", wilson_ci(20, 100)),
        _cycle("c1", "live", wilson_ci(80, 100)),
        _cycle("c2", "live", wilson_ci(20, 100)),
    ]
    d = decide(cycles, WV)
    assert d.action == "ROLLBACK"
    assert any("CONTRADICTION" in line for line in d.reasoning)


def test_decide_refuses_mixed_source_history():
    cycles = [
        _cycle("c0", "live", wilson_ci(50, 100)),
        _cycle("c1", "synthetic", wilson_ci(60, 100)),
        _cycle("c2", "live", wilson_ci(70, 100)),
    ]
    try:
        decide(cycles, WV)
        assert False, "expected GatingError"
    except GatingError:
        pass
