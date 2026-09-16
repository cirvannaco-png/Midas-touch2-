"""Execution outcome boundary: execution quality feeds measurement, not alpha intent."""

from dataclasses import dataclass

from .execution_models import ExecutionOutcome, OrderStatus


@dataclass(frozen=True)
class OutcomeObservation:
    order_id: str
    decision_id: str
    symbol: str
    regime: str
    policy: str
    venue: str | None
    requested_quantity: float
    filled_quantity: float
    implementation_shortfall: float | None
    slippage_cost: float
    market_impact_cost: float
    surveillance_codes: tuple[str, ...]


def to_observation(outcome: ExecutionOutcome, *, regime: str, policy: str, venue: str | None) -> OutcomeObservation:
    return OutcomeObservation(
        order_id=outcome.order_id,
        decision_id=outcome.decision_id,
        symbol=outcome.symbol,
        regime=regime,
        policy=policy,
        venue=venue,
        requested_quantity=outcome.requested_quantity,
        filled_quantity=outcome.filled_quantity,
        implementation_shortfall=outcome.tca.implementation_shortfall,
        slippage_cost=outcome.tca.slippage_cost,
        market_impact_cost=outcome.tca.market_impact_cost,
        surveillance_codes=outcome.surveillance_codes,
    )


def eligible_for_alpha_calibration(outcome: ExecutionOutcome) -> bool:
    """Execution outcome is eligible for alpha outcome processing only when resolved."""
    return outcome.status == OrderStatus.FILLED and outcome.filled_quantity > 0 and outcome.reconciled
