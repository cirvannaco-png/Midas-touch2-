import pytest

from app import calibration


@pytest.mark.asyncio
async def test_no_recent_live_outcomes_still_evaluates_registered_candidates(monkeypatch):
    calls = {"evaluate": 0, "cards": []}

    async def no_rows(_since):
        return []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def evaluate_candidates(session):
        assert session is not None
        calls["evaluate"] += 1
        return {
            "status": "policy_not_configured",
            "promotions": 0,
            "holds": 1,
            "promotion_ids": [],
        }

    async def send_cards(ids):
        calls["cards"] = list(ids)

    monkeypatch.setattr(calibration, "_fetch_window_rows", no_rows)
    monkeypatch.setattr(calibration, "async_session", lambda: FakeSession())
    monkeypatch.setattr(calibration, "evaluate_registered_challengers", evaluate_candidates)
    monkeypatch.setattr(calibration, "_send_config_promotion_cards", send_cards)

    result = await calibration.run_cycle()

    assert result["status"] == "no_data"
    assert result["config_lifecycle"]["status"] == "policy_not_configured"
    assert calls["evaluate"] == 1
    assert calls["cards"] == []
