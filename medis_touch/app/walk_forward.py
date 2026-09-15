"""Leakage-resistant walk-forward validation window construction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def build_windows(
    observations: Sequence[object],
    *,
    train_size: int,
    test_size: int,
    step: int | None = None,
) -> tuple[WalkForwardWindow, ...]:
    """Build sequential train/test windows with strict temporal separation."""
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    step = test_size if step is None else step
    if step <= 0:
        raise ValueError("step must be positive")
    windows = []
    start = 0
    index = 0
    total = len(observations)
    while start + train_size + test_size <= total:
        train_end = start + train_size
        test_end = train_end + test_size
        windows.append(WalkForwardWindow(index, start, train_end, train_end, test_end))
        index += 1
        start += step
    return tuple(windows)


def evaluate(
    observations: Sequence[object],
    *,
    train_size: int,
    test_size: int,
    trainer,
    evaluator,
    step: int | None = None,
):
    """Train only on each window's historical segment and evaluate only on its OOS segment."""
    windows = build_windows(observations, train_size=train_size, test_size=test_size, step=step)
    results = []
    for window in windows:
        model = trainer(observations[window.train_start:window.train_end])
        result = evaluator(model, observations[window.test_start:window.test_end])
        results.append(result)
    return tuple(results)
