"""Trade-event HTTP boundary contract for Phase B.

No endpoint is registered here yet. The legacy route remains authoritative
until the trade route family can be moved with regression evidence and no
public-contract drift.
"""

from fastapi import HTTPException

from app.validator import validate_trade_event


def validate_trade_request(payload: dict) -> None:
    """Apply the existing trade-event validation contract unchanged."""
    valid, errors = validate_trade_event(payload)
    if not valid:
        raise HTTPException(
            status_code=400,
            detail={"event_id": payload.get("event_id"), "errors": errors},
        )


__all__ = ["validate_trade_request"]
