"""Pure parent-to-child scheduler; submission remains owned by the governed coordinator."""

from dataclasses import replace

from .execution_models import ExecutionOrder, ExecutionPolicy, OrderStatus
from .execution_policy import pov_schedule, twap_schedule, vwap_schedule


class ChildOrderExecutor:
    """Create deterministic child orders without bypassing OMS/risk/governance."""

    def schedule(self, order: ExecutionOrder, *, observed_volumes: list[float] | None = None) -> tuple[float, ...]:
        if order.quantity <= 0:
            raise ValueError("parent quantity must be positive")
        if order.policy == ExecutionPolicy.TWAP:
            return twap_schedule(order.quantity, int(order.metadata.get("slices", 1)))
        if order.policy == ExecutionPolicy.VWAP:
            if observed_volumes is None:
                raise ValueError("VWAP requires an observed volume profile")
            return vwap_schedule(order.quantity, observed_volumes)
        if order.policy == ExecutionPolicy.POV:
            if observed_volumes is None:
                raise ValueError("POV requires observed volumes")
            return pov_schedule(order.quantity, observed_volumes, float(order.metadata.get("participation", 0.1)))
        return (order.quantity,)

    def build_children(self, order: ExecutionOrder, *, observed_volumes: list[float] | None = None) -> tuple[ExecutionOrder, ...]:
        children: list[ExecutionOrder] = []
        for index, quantity in enumerate(self.schedule(order, observed_volumes=observed_volumes)):
            if quantity <= 0:
                continue
            child = replace(
                order,
                order_id=f"{order.order_id}:child:{index}",
                quantity=quantity,
                status=OrderStatus.NEW,
                idempotency_key=f"{order.idempotency_key or order.order_id}:child:{index}",
                metadata={**order.metadata, "parent_order_id": order.order_id, "child_index": index},
            )
            children.append(child)
        if abs(sum(child.quantity for child in children) - order.quantity) > 1e-10:
            raise RuntimeError("child quantities do not conserve parent quantity")
        return tuple(children)
