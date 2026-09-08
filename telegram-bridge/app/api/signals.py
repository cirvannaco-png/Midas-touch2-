"""Signal HTTP boundary contract for Phase B.

The legacy route remains registered in ``app.routes`` until the complete
signal route family is extracted and regression-tested. This module therefore
contains only boundary helpers and does not register duplicate endpoints.
"""

from fastapi import HTTPException

from app.validator import validate_signal


def validate_signal_request(payload: dict) -> None:
    """Apply the existing signal validation contract without changing it."""
    valid, errors = validate_signal(payload)
    if not valid:
        signal_id = payload.get("signal_id")
        raise HTTPException(
            status_code=400,
            detail={"signal_id": signal_id, "errors": errors},
        )


__all__ = ["validate_signal_request"]
