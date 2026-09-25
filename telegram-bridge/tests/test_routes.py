from unittest.mock import AsyncMock, patch

from tests.conftest import VALID_BUY_SIGNAL


def test_health_check_no_auth_required(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "online"
    assert body["database"] == "not checked"


def test_health_db_reports_connected(client):
    resp = client.get("/health/db")
    assert resp.status_code == 200
    assert resp.json()["database"] == "connected"

def test_health_db_reports_unhealthy_when_database_is_down(client):
    with patch("app.routes.check_db_connection", new=AsyncMock(return_value=False)):
        resp = client.get("/health/db")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"
    assert resp.json()["database"] == "disconnected"


def test_signal_without_api_key_rejected(client):
    resp = client.post("/signal", json=VALID_BUY_SIGNAL)
    assert resp.status_code == 422  # missing required header


def test_signal_with_wrong_api_key_rejected(client):
    resp = client.post("/signal", json=VALID_BUY_SIGNAL, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_valid_signal_accepted_and_queued(client, auth_headers):
    payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-accept-1"}
    resp = client.post("/signal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert len(body["decision_fingerprint"]) == 64


def test_benchmark_signal_is_disabled_by_default(client):
    payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-benchmark-disabled-1"}
    resp = client.post("/benchmark/signal", json=payload, headers={"X-API-Key": "bench-secret"})
    assert resp.status_code == 404


def test_benchmark_signal_is_read_only_when_enabled(client, auth_headers):
    from app.config import settings
    from app.database import async_session
    from app.models import Signal, SignalDeliveryOutbox
    from sqlalchemy import func, select

    original_enabled = settings.BENCHMARK_ENABLED
    original_key = settings.BENCHMARK_API_KEY
    settings.BENCHMARK_ENABLED = True
    settings.BENCHMARK_API_KEY = "bench-secret"
    try:
        payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-benchmark-readonly-1"}
        resp = client.post(
            "/benchmark/signal",
            json=payload,
            headers={"X-API-Key": "bench-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert len(resp.json()["decision_fingerprint"]) == 64

        async def _counts():
            async with async_session() as session:
                signal_count = await session.scalar(select(func.count()).select_from(Signal))
                outbox_count = await session.scalar(select(func.count()).select_from(SignalDeliveryOutbox))
                return signal_count, outbox_count

        assert client.portal is not None
        signal_count, outbox_count = client.portal.call(_counts)
        assert signal_count == 0
        assert outbox_count == 0
    finally:
        settings.BENCHMARK_ENABLED = original_enabled
        settings.BENCHMARK_API_KEY = original_key


def test_valid_signal_and_outbox_commit_together(client, auth_headers):
    """A valid signal and its durable delivery reservation must commit together."""
    from app.database import async_session
    from app.models import Signal, SignalDeliveryOutbox, SignalStatus
    from sqlalchemy import select

    payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-atomic-1"}
    resp = client.post("/signal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

    async def _read_rows():
        async with async_session() as session:
            signal = await session.scalar(select(Signal).where(Signal.signal_id == payload["signal_id"]))
            outbox = await session.scalar(
                select(SignalDeliveryOutbox).where(SignalDeliveryOutbox.signal_id == payload["signal_id"])
            )
            return signal, outbox

    assert client.portal is not None
    signal, outbox = client.portal.call(_read_rows)
    assert signal is not None
    assert signal.status == SignalStatus.PENDING
    assert outbox is not None
    assert outbox.status == "pending"


def test_suppressed_signal_is_recorded_without_delivery_outbox(client, auth_headers):
    from app.database import async_session
    from app.models import Signal, SignalDeliveryOutbox, SignalStatus
    from sqlalchemy import select

    payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-suppressed-1"}
    with patch("app.routes.get_signal_broadcast_controls", new=AsyncMock(return_value=(True, set()))):
        resp = client.post("/signal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "suppressed"

    async def _read_rows():
        async with async_session() as session:
            signal = await session.scalar(select(Signal).where(Signal.signal_id == payload["signal_id"]))
            outbox = await session.scalar(
                select(SignalDeliveryOutbox).where(SignalDeliveryOutbox.signal_id == payload["signal_id"])
            )
            return signal, outbox

    assert client.portal is not None
    signal, outbox = client.portal.call(_read_rows)
    assert signal is not None
    assert signal.status == SignalStatus.ACTIVE
    assert outbox is None


def test_legacy_signal_is_recorded_but_accepted_when_strict_fingerprint_is_disabled(client, auth_headers):
    from app.config import settings
    original = settings.REQUIRE_DECISION_FINGERPRINT
    settings.REQUIRE_DECISION_FINGERPRINT = False
    try:
        payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-legacy-1"}
        resp = client.post("/signal", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"
    finally:
        settings.REQUIRE_DECISION_FINGERPRINT = original


def test_legacy_signal_is_rejected_when_strict_fingerprint_is_enabled(client, auth_headers):
    from app.config import settings
    original = settings.REQUIRE_DECISION_FINGERPRINT
    settings.REQUIRE_DECISION_FINGERPRINT = True
    try:
        payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-legacy-strict-1"}
        resp = client.post("/signal", json=payload, headers=auth_headers)
        assert resp.status_code == 428
        assert resp.json()["detail"]["code"] == "FINGERPRINT_REQUIRED"
    finally:
        settings.REQUIRE_DECISION_FINGERPRINT = original


def test_business_rule_violation_rejected(client, auth_headers):
    payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-bad-1", "sl": 1.15}  # SL wrong side
    resp = client.post("/signal", json=payload, headers=auth_headers)
    assert resp.status_code == 400
    assert "errors" in resp.json()["detail"]


def test_invalid_direction_rejected_by_schema(client, auth_headers):
    payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-bad-2", "direction": "HOLD"}
    resp = client.post("/signal", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_duplicate_signal_id_returns_duplicate_status(client, auth_headers):
    payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-dup-1"}
    first = client.post("/signal", json=payload, headers=auth_headers)
    second = client.post("/signal", json=payload, headers=auth_headers)
    assert first.json()["status"] == "queued"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert second.json()["duplicate"] is True


def test_rate_limit_enforced_after_max_requests(client, auth_headers, forced_rate_limit):
    # The limiter is force-enabled at max_requests=5 by the fixture, so this
    # test does not depend on RATE_LIMIT_* env vars (CI sets
    # RATE_LIMIT_ENABLED=false, which would otherwise make 429 unreachable).
    codes = []
    for i in range(7):
        payload = {**VALID_BUY_SIGNAL, "signal_id": f"sig-rl-{i}"}
        resp = client.post("/signal", json=payload, headers=auth_headers)
        codes.append(resp.status_code)
    assert codes[:5] == [200] * 5
    assert codes[5:] == [429, 429]


def test_queued_signal_does_not_wait_for_telegram(client, auth_headers):
    with patch("app.signal_outbox.send_telegram_message", new=AsyncMock(side_effect=RuntimeError("telegram unavailable"))):
        payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-async-1"}
        resp = client.post("/signal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_telegram_send_failure_isolated_from_signal_acceptance(client, auth_headers):
    with patch("app.signal_outbox.send_telegram_message", new=AsyncMock(side_effect=RuntimeError("boom"))):
        payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-fail-1"}
        resp = client.post("/signal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"



def test_retry_failed_requires_auth(client):
    resp = client.post("/retry-failed")
    assert resp.status_code == 422


def test_retry_failed_with_no_failed_signals(client, auth_headers):
    resp = client.post("/retry-failed", headers=auth_headers)
    assert resp.status_code == 200
    assert "No failed signals" in resp.json()["message"]


def test_signal_id_reserved_before_telegram_is_called_once(client, auth_headers):
    """
    Regression test for the double-send race: a signal_id that has already
    been reserved (PENDING row present) must short-circuit to "duplicate"
    without calling Telegram again, even if the first request never
    resolved. This is what actually prevents two Telegram messages for one
    signal_id under a real concurrent race - previously the reservation
    didn't exist and both requests could reach send_telegram_message.
    """

    from app.database import async_session
    from app.models import Signal, SignalStatus

    payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-race-1"}

    async def _seed_pending_row():
        async with async_session() as session:
            session.add(Signal(
                signal_id=payload["signal_id"],
                symbol=payload["symbol"],
                direction=payload["direction"],
                entry=payload["entry"],
                sl=payload["sl"],
                tp1=payload["tp1"],
                tp2=payload["tp2"],
                confidence=payload["confidence"],
                reasons=payload["reasons"],
                timeframe=payload["timeframe"],
                status=SignalStatus.PENDING,
            ))
            await session.commit()

    assert client.portal is not None
    client.portal.call(_seed_pending_row)

    with patch("app.routes.send_telegram_message", new=AsyncMock(return_value=99)) as mock_send:
        resp = client.post("/signal", json=payload, headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "duplicate"
    mock_send.assert_not_called()


def test_retry_failed_reclaims_stale_pending_rows(client, auth_headers):
    """A row stuck at PENDING (e.g. process crashed mid-send) older than
    PENDING_STALE_SECONDS should be picked up by /retry-failed, same as a
    FAILED row - otherwise it never recovers."""
    from datetime import datetime, timedelta, timezone

    from app.database import async_session
    from app.models import Signal, SignalStatus

    payload = {**VALID_BUY_SIGNAL, "signal_id": "sig-stale-pending-1"}
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=999)

    async def _seed_stale_pending_row():
        async with async_session() as session:
            session.add(Signal(
                signal_id=payload["signal_id"],
                symbol=payload["symbol"],
                direction=payload["direction"],
                entry=payload["entry"],
                sl=payload["sl"],
                tp1=payload["tp1"],
                tp2=payload["tp2"],
                confidence=payload["confidence"],
                reasons=payload["reasons"],
                timeframe=payload["timeframe"],
                status=SignalStatus.PENDING,
                received_at=stale_time,
            ))
            await session.commit()

    assert client.portal is not None
    client.portal.call(_seed_stale_pending_row)

    resp = client.post("/retry-failed", headers=auth_headers)
    assert resp.status_code == 200
    assert "Processed 1 failed signals" in resp.json()["message"]


def test_signal_warm_latency_regression_ceiling(client, auth_headers):
    """Warm-path guard with enough samples for distinct p95/p99 nearest-rank checks."""
    import math
    import time

    from app.ratelimit import rate_limiter

    original = (rate_limiter.enabled, rate_limiter.max_requests, rate_limiter.window_seconds)
    rate_limiter.enabled = False
    try:
        samples_ms = []
        for i in range(100):
            payload = {**VALID_BUY_SIGNAL, "signal_id": f"sig-latency-{i}"}
            start_time = time.perf_counter()
            response = client.post("/signal", json=payload, headers=auth_headers)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            assert response.status_code == 200
            samples_ms.append(elapsed_ms)
    finally:
        rate_limiter.enabled, rate_limiter.max_requests, rate_limiter.window_seconds = original

    samples_ms.sort()
    p50 = samples_ms[len(samples_ms) // 2]
    p95 = samples_ms[max(0, math.ceil(0.95 * len(samples_ms)) - 1)]
    p99 = samples_ms[max(0, math.ceil(0.99 * len(samples_ms)) - 1)]
    assert p50 < 150.0, f"warm /signal p50 regression: {p50:.1f} ms"
    assert p95 < 250.0, f"warm /signal p95 regression: {p95:.1f} ms"
    assert p99 < 300.0, f"warm /signal p99 regression: {p99:.1f} ms"
