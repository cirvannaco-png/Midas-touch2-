"""Copy-feed HTTP boundary.

The public route contract remains owned by app.routes during Phase B. This
module isolates the authorization behavior first so Phase C can consume the
service boundary without changing status codes or signal-query semantics.
"""

from fastapi import HTTPException

from app.services.copy_authorization import (
    CopyFeedKeyUnknown,
    CopyFeedNotEntitled,
    authorize_copy_feed,
)


async def authorize_copy_feed_request(session, copy_key: str):
    """Translate service authorization failures to the existing HTTP contract."""
    try:
        return await authorize_copy_feed(session, copy_key)
    except CopyFeedKeyUnknown:
        raise HTTPException(status_code=401, detail="Unrecognized copy-feed key")
    except CopyFeedNotEntitled:
        raise HTTPException(
            status_code=403,
            detail="Copy trading is not currently active for this subscriber",
        )
