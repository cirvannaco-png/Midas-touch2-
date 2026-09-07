"""Subscriber copy-feed authorization service boundary.

The existing route remains the compatibility API. This service is the seam
for Phase C extraction and deliberately delegates to the established
can_copy() implementation rather than duplicating entitlement logic.
"""

from app.copy_trading import can_copy
from app.subscriptions import get_subscriber_by_copy_feed_key


async def authorize_copy_feed(session, copy_key: str):
    """Resolve and authorize a subscriber; return None when unknown/denied."""
    subscriber = await get_subscriber_by_copy_feed_key(session, copy_key)
    if subscriber is None:
        return None
    if not await can_copy(session, subscriber):
        return None
    return subscriber
