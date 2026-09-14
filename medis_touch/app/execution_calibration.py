"""Execution-quality calibration kept separate from alpha-confidence calibration."""

from dataclasses import dataclass

from .execution_outcome import OutcomeObservation


@dataclass(frozen=True)
class ExecutionCalibrationRecord:
    order_id: str
    decision_id: str
    regime: str
    policy: str
    venue: str | None
    filled_ratio: float
    implementation_shortfall: float | None
    slippage_cost: float
    market_impact_cost: float


def record_from_outcome(observation: OutcomeObservation) -> ExecutionCalibrationRecord:
    if observation.requested_quantity <= 0:
        raise ValueError("requested quantity must be positive")
    if observation.filled_quantity < 0 or observation.filled_quantity > observation.requested_quantity + 1e-12:
        raise ValueError("filled quantity is outside parent quantity bounds")
    return ExecutionCalibrationRecord(
        order_id=observation.order_id,
        decision_id=observation.decision_id,
        regime=observation.regime,
        policy=observation.policy,
        venue=observation.venue,
        filled_ratio=observation.filled_quantity / observation.requested_quantity,
        implementation_shortfall=observation.implementation_shortfall,
        slippage_cost=observation.slippage_cost,
        market_impact_cost=observation.market_impact_cost,
    )
