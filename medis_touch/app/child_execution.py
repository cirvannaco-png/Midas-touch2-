"""Child-order execution coordinator for TWAP/VWAP/POV policies."""
from __future__ import annotations

from dataclasses import replace

from .execution_models import ExecutionOrder, ExecutionPolicy, OrderStatus
from .execution_policy import pov_schedule, twap_schedule, vwap_schedule
from .venue import ExecutionVenue


class ChildOrderExecutor:
    """Create and submit deterministic child orders through an approved venue."""

    def __init__(self, venue: ExecutionVenue) -> None:
        self.venue = venue

    def schedule(self, order: ExecutionOrder, *, observed_volumes: list[float] | None = None) -> tuple[float, ...]:
        if order.quantity <= 0:
            raise ValueError("parent quantity must be positive")
        if order.policy == ExecutionPolicy.TWAP:
            slices = int(order.metadata.get("slices", 1))
            return twap_schedule(order.quantity, slices)
        if order.policy == ExecutionPolicy.VWAP:
            if observed_volumes is None:
                raise ValueError("VWAP requires an observed volume profile")
            return vwap_schedule(order.quantity, observed_volumes)
        if order.policy == ExecutionPolicy.POV:
            if observed_volumes is None:
                raise ValueError("POV requires observed volumes")
            participation = float(order.metadata.get("participation", 0.1))
            return pov_schedule(order.quantity, observed_volumes, participation)
        return (order.quantity,)

    def submit_children(
        self,
        order: ExecutionOrder,
        *,
        observed_volumes: list[float] | None = None,
    ) -> tuple[ExecutionOrder, ...]:
        children: list[ExecutionOrder] = []
        for index, quantity in enumerate(self.schedule(order, observed_volumes=observed_volumes)):
            if quantity <= 0:
                continue
            child = replace(
                order,
                order_id=f"{order.order_id}:child:{index}",
                quantity=quantity,
                status=OrderStatus.ROUTING,
                idempotency_key=f"{order.idempotency_key or order.order_id}:child:{index}",
                metadata={**order.metadata, "parent_order_id": order.order_id, "child_index": index},
            )
            self.venue.submit(child)
            children.append(child)
        return tuple(children)
