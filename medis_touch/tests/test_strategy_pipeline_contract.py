from datetime import datetime, timezone

from medis_touch.app.models import OrderType, TradeSetup
from medis_touch.app.strategy_engines import MarketContext, SetupEngine
from medis_touch.app.strategy_pipeline import (
    AuthoritativeStrategyPipeline,
    StrategyCandidate,
    validate_complete_setup,
)


class _Context(MarketContext):
    pass


class _Engine(SetupEngine):
    name = "test_strategy"

    def detect(self, ctx: MarketContext) -> bool:
        return True

    def build_setup(self, ctx: MarketContext, now: datetime) -> TradeSetup:
        return TradeSetup(
            type=OrderType.BUY,
            entry_top=101.0,
            entry_bottom=100.0,
            invalidation=99.0,
            stop_loss=98.5,
            tp1=102.0,
            tp2=103.0,
            final_tp=104.0,
            confidence=80.0,
            creation_time=now,
        )


def test_selected_engine_is_the_only_source_of_the_setup():
    now = datetime.now(timezone.utc)
    pipeline = AuthoritativeStrategyPipeline({"test_strategy": _Engine()})

    result = pipeline.build(StrategyCandidate("test_strategy", 90.0), _Context(), now)

    assert result is not None
    assert result.strategy == "test_strategy"
    assert result.setup.invalidation == 99.0
    assert result.setup.stop_loss == 98.5


def test_missing_selected_engine_fails_closed():
    now = datetime.now(timezone.utc)
    pipeline = AuthoritativeStrategyPipeline({})

    assert pipeline.build(StrategyCandidate("missing", 100.0), _Context(), now) is None


def test_malformed_target_ladder_fails_closed():
    now = datetime.now(timezone.utc)
    setup = TradeSetup(
        type=OrderType.BUY,
        entry_top=101.0,
        entry_bottom=100.0,
        invalidation=99.0,
        stop_loss=98.5,
        tp1=102.0,
        tp2=101.5,
        final_tp=104.0,
        confidence=80.0,
        creation_time=now,
    )

    try:
        validate_complete_setup(setup)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid target ladder must fail closed")
