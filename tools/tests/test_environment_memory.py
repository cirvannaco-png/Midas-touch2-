from dataclasses import dataclass
from pathlib import Path

from tools.environment_memory import aggregate, wilson_interval

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


@dataclass
class Row:
    symbol: str = "EURUSD"
    strategy: str = "STRATEGY_MOMENTUM_BREAKOUT"
    environment_key: str = "env-A"
    outcome: str = "win"
    realized_r: float | None = 1.0
    mae_r: float | None = 0.2
    mfe_r: float | None = 1.5
    bars_held: int | None = 5
    received_at: int = 0
    environment: dict | None = None
    regime: str | None = "REGIME_TRENDING"
    session: str | None = "SESSION_LONDON"


def test_wilson_interval_is_bounded_and_ordered():
    low, high = wilson_interval(30, 50)
    assert 0.0 <= low <= high <= 1.0


def test_positive_cell_requires_minimum_sample_and_can_qualify():
    rows = [Row(received_at=i) for i in range(30)]
    evidence = next(iter(aggregate(rows, min_sample=30).values()))
    assert evidence.status == "QUALIFIED"
    assert evidence.adjustment > 0
    assert evidence.profit_factor > 1.0


def test_small_loss_streak_cannot_degrade_strategy():
    rows = [Row(outcome="loss", realized_r=-1.0, received_at=0)] + [Row(received_at=i) for i in range(1, 10)]
    evidence = next(iter(aggregate(rows, min_sample=30).values()))
    assert evidence.status == "UNKNOWN"
    assert evidence.adjustment == 0.0


def test_negative_cell_needs_hysteresis_threshold():
    rows = [Row(outcome="loss", realized_r=-1.0, received_at=i) for i in range(60)]
    evidence = next(iter(aggregate(rows, min_sample=30).values()))
    assert evidence.status == "DEGRADED"
    assert evidence.adjustment < 0


def test_restart_safe_storage_contract_is_present_in_ea_memory():
    memory = _read("EA/includes/Trading/EnvironmentStrategyMemory.mqh")
    assert "void Save() const" in memory
    assert "void Load()" in memory
    assert "Load();" in memory
    assert "Save();" in memory
    assert "m_degradedMinSample=m_minSample*2" in memory


def test_backtest_memory_isolated_from_persistent_live_history():
    memory = _read("EA/includes/Trading/EnvironmentStrategyMemory.mqh")
    assert "m_persistent=(MQLInfoInteger(MQL_TESTER)==0)" in memory
    assert "if(!m_persistent||StringLen(m_filename)==0)return;" in memory
    assert "if(!m_persistent||StringLen(m_filename)==0||!FileIsExist(m_filename))return;" in memory


def test_adaptive_router_uses_historical_evidence_but_keeps_raw_score_authoritative():
    router = _read("EA/includes/Trading/StrategyTradeZone.mqh")
    assert "GetEvidence(reasons,challenger,challengerEvidence)" in router
    assert "GetEvidence(reasons,STRATEGY_SMC,smcEvidence)" in router
    assert "challengerAdjusted=challengerScore+challengerEvidence.adjustment" in router
    assert "smcAdjusted=smcScore+smcEvidence.adjustment" in router
    assert "selectedScore=challengerScore" in router
    assert "selectedScore=smcScore" in router


def test_ci_remains_explicitly_paused():
    ci = _read(".gitlab-ci.yml")
    assert "workflow:" in ci
    assert "- when: never" in ci
