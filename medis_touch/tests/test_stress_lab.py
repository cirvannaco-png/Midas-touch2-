from medis_touch.app.institutional_control import ControlInputs, ControlState
from medis_touch.app.stress_lab import StressCase, all_passed, run


def test_default_stress_matrix_passes():
    results = run()
    assert all_passed(results)
    assert all(result.passed for result in results)


def test_stress_evaluator_is_called_once_per_case():
    calls = []

    def evaluator(inputs: ControlInputs) -> ControlState:
        calls.append(inputs)
        return ControlState.NORMAL

    cases = (StressCase("one", ControlInputs(True, True, True, True, True), ControlState.NORMAL),)
    results = run(cases, evaluator)
    assert results[0].passed
    assert len(calls) == 1
