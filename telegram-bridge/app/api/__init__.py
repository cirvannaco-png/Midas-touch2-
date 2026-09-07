"""HTTP API router package for the Medis Touch bridge.

Phase B is intentionally incremental: endpoint implementations remain in
app.routes until each route family has been extracted and regression-tested.
This package provides the stable aggregate-router seam without registering
any duplicate endpoints during the transition.
"""

from fastapi import APIRouter

router = APIRouter()

__all__ = ["router"]
