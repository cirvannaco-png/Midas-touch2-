"""Subscriber copy-feed authorization service boundary.

The existing route remains the compatibility API. This service owns the
subscriber lookup + entitlement decision seam without changing the public
HTTP contract: unknown keys remain 401 and known-but-ineligible subscribers
remain 403.
"""

from app.copy_trading import can_copy
from app.subscriptions import get_subscriber_by_copy_feed_key


class CopyAuthorizationDenied(PermissionError):
    """Base error for fail-closed copy-feed authorization."""


class CopyFeedKeyUnknown(CopyAuthorizationDenied):
    """The supplied copy-feed key does not identify a subscriber."""


class CopyFeedNotEntitled(CopyAuthorizationDenied):
    """The subscriber exists but is not currently permitted to copy."""


async def authorize_copy_feed(session, copy_key: str):
    """Resolve and authorize a subscriber; fail closed on unknown/denied."""
    subscriber = await get_subscriber_by_copy_feed_key(session, copy_key)
    if subscriber is None:
        raise CopyFeedKeyUnknown("Unrecognized copy-feed key")
    if not await can_copy(session, subscriber):
        raise CopyFeedNotEntitled("Copy trading is not currently active for this subscriber")
    return subscriber
