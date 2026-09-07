"""Admin HTTP boundary contract for Phase B.

Admin endpoints remain owned by ``app.routes`` during incremental extraction.
Shared API-key authentication continues to be the existing dependency until
an active router module can be introduced and regression-tested.
"""

from app.routes import verify_api_key


__all__ = ["verify_api_key"]
