import pytest
from fastapi import HTTPException

from app.api import router
from app.api.copy_feed import authorize_copy_feed_request


def test_phase_b_api_router_exists_without_duplicate_registration():
    assert router.routes == []


@pytest.mark.asyncio
async def test_copy_feed_unknown_key_preserves_401(monkeypatch):
    async def deny(*args, **kwargs):
        from app.services.copy_authorization import CopyFeedKeyUnknown
        raise CopyFeedKeyUnknown()

    monkeypatch.setattr("app.api.copy_feed.authorize_copy_feed", deny)
    with pytest.raises(HTTPException) as exc:
        await authorize_copy_feed_request(object(), "bad-key")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_copy_feed_ineligible_subscriber_preserves_403(monkeypatch):
    async def deny(*args, **kwargs):
        from app.services.copy_authorization import CopyFeedNotEntitled
        raise CopyFeedNotEntitled()

    monkeypatch.setattr("app.api.copy_feed.authorize_copy_feed", deny)
    with pytest.raises(HTTPException) as exc:
        await authorize_copy_feed_request(object(), "known-key")
    assert exc.value.status_code == 403
