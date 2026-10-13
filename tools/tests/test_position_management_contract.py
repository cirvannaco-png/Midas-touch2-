from pathlib import Path


def test_partial_close_is_not_coupled_to_trailing_stop_modification():
    root = Path(__file__).resolve().parents[2]
    manager = (root / "EA/includes/Execution/PositionManager.mqh").read_text(encoding="utf-8")
    policy = (root / "EA/includes/Execution/PositionManagementPolicy.mqh").read_text(encoding="utf-8")
    assert '#include "PositionManagementPolicy.mqh"' in manager
    assert "ShouldTakePartialAtR(stateAfterStop,r,m_partialAtR)" in manager
    assert "stateAfterStop==TS_PROTECTED && r>=m_partialAtR" not in manager
    assert "state==TS_FILLED || state==TS_PROTECTED" in policy
