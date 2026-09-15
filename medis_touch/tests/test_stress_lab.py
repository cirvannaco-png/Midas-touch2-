from medis_touch.app.institutional_control import ControlState
from medis_touch.app.stress_lab import all_passed, run


def test_default_stress_lab_passes_all_control_invariants():
    results = run()
    assert all_passed(results)
    assert all(result.actual_state is result.expected_state for result in results)


def test_stress_lab_contains_critical_and_degraded_paths():
    names = {result.name for result in run()}
    assert {"broker_disconnect", "duplicate_order", "model_drift", "normal"}.issubset(names)
    assert any(result.actual_state is ControlState.HALTED for result in run())
