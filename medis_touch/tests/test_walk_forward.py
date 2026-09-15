from medis_touch.app.walk_forward import build_windows, evaluate


def test_walk_forward_windows_never_overlap_train_and_test():
    observations = list(range(12))
    windows = build_windows(observations, train_size=4, test_size=2, step=2)
    assert windows[0].train_start == 0
    assert windows[0].train_end == windows[0].test_start == 4
    assert windows[0].test_end == 6
    assert all(window.train_end <= window.test_start for window in windows)


def test_walk_forward_evaluate_only_receives_oos_slice():
    observations = list(range(8))
    seen = []

    def trainer(train):
        seen.append(("train", tuple(train)))
        return sum(train)

    def evaluator(model, test):
        seen.append(("test", tuple(test)))
        return model, tuple(test)

    results = evaluate(observations, train_size=3, test_size=2, trainer=trainer, evaluator=evaluator)
    assert results[0] == (3, (3, 4))
    assert seen[0] == ("train", (0, 1, 2))
    assert seen[1] == ("test", (3, 4))
