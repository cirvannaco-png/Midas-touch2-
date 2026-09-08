import asyncio

from app.config_registry import ConfigurationIdentity
from app.config_registry_model import ConfigurationRegistry
from app.database import async_session


def make_identity(*, strategy="SMC", instrument="XAUUSD", timeframe="M15", threshold=90):
    return ConfigurationIdentity(
        strategy=strategy,
        instrument=instrument,
        timeframe=timeframe,
        parameters={"confidence_threshold": threshold},
        data_version="data-2026-09-01",
        optimizer_version="optimizer-1",
    )


def seed_registry(*identities_and_statuses):
    async def _seed():
        async with async_session() as session:
            for identity, status in identities_and_statuses:
                row = ConfigurationRegistry.from_identity(identity)
                for target in ("BACKTESTED", "VALIDATED", "QUARANTINE", "SHADOW", "CHALLENGER", "CHAMPION"):
                    if target == status:
                        if target != "OPTIMIZED":
                            row.transition_to(target)
                        break
                    row.transition_to(target)
                session.add(row)
            await session.commit()

    asyncio.run(_seed())


def test_get_config_returns_verified_champion(client, auth_headers):
    identity = make_identity()
    seed_registry((identity, "CHAMPION"))

    response = client.get("/config/XAUUSD", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["config_hash"] == identity.config_hash
    assert body["instrument"] == "XAUUSD"
    assert body["lifecycle_status"] == "CHAMPION"
    assert body["active"] is False


def test_get_config_fails_when_no_champion_exists(client, auth_headers):
    identity = make_identity()
    seed_registry((identity, "CHALLENGER"))

    response = client.get("/config/XAUUSD", headers=auth_headers)

    assert response.status_code == 404


def test_ack_requires_exact_registered_hash_and_metadata(client, auth_headers):
    identity = make_identity()
    seed_registry((identity, "CHAMPION"))

    wrong = client.post(
        "/config/XAUUSD/ack",
        headers=auth_headers,
        json={
            "config_hash": "b" * 64,
            "strategy": identity.strategy,
            "timeframe": identity.timeframe,
            "version": 1,
        },
    )
    assert wrong.status_code == 404

    mismatch = client.post(
        "/config/XAUUSD/ack",
        headers=auth_headers,
        json={
            "config_hash": identity.config_hash,
            "strategy": "OTHER",
            "timeframe": identity.timeframe,
            "version": 1,
        },
    )
    assert mismatch.status_code == 200
    assert mismatch.json()["action"] == "HOLD"


def test_exact_ack_activates_and_get_reports_active(client, auth_headers):
    identity = make_identity()
    seed_registry((identity, "CHAMPION"))

    ack = client.post(
        "/config/XAUUSD/ack",
        headers=auth_headers,
        json={
            "config_hash": identity.config_hash,
            "strategy": identity.strategy,
            "timeframe": identity.timeframe,
            "version": 1,
        },
    )

    assert ack.status_code == 200
    assert ack.json()["action"] == "ACTIVATE"
    assert ack.json()["state"] == "ACTIVE"

    response = client.get("/config/XAUUSD", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["active"] is True


def test_runtime_rejects_unknown_or_non_active_hash(client, auth_headers):
    identity = make_identity()
    seed_registry((identity, "CHAMPION"))

    unknown = client.post(
        "/config/XAUUSD/runtime",
        headers=auth_headers,
        json={"config_hash": "c" * 64, "healthy": True},
    )
    assert unknown.status_code == 404

    not_active = client.post(
        "/config/XAUUSD/runtime",
        headers=auth_headers,
        json={"config_hash": identity.config_hash, "healthy": True},
    )
    assert not_active.status_code == 409


def test_unhealthy_challenger_rolls_back_to_champion(client, auth_headers):
    champion = make_identity(threshold=90)
    challenger = make_identity(threshold=91)
    seed_registry((champion, "CHAMPION"), (challenger, "CHALLENGER"))

    ack = client.post(
        "/config/XAUUSD/ack",
        headers=auth_headers,
        json={
            "config_hash": challenger.config_hash,
            "strategy": challenger.strategy,
            "timeframe": challenger.timeframe,
            "version": 1,
        },
    )
    assert ack.status_code == 200
    assert ack.json()["action"] == "ACTIVATE"

    runtime = client.post(
        "/config/XAUUSD/runtime",
        headers=auth_headers,
        json={"config_hash": challenger.config_hash, "healthy": False},
    )

    assert runtime.status_code == 200
    assert runtime.json()["action"] == "ROLLBACK"
    assert runtime.json()["active_config_hash"] == champion.config_hash


def test_unhealthy_champion_enters_defensive_state(client, auth_headers):
    champion = make_identity()
    seed_registry((champion, "CHAMPION"))

    ack = client.post(
        "/config/XAUUSD/ack",
        headers=auth_headers,
        json={
            "config_hash": champion.config_hash,
            "strategy": champion.strategy,
            "timeframe": champion.timeframe,
            "version": 1,
        },
    )
    assert ack.status_code == 200

    runtime = client.post(
        "/config/XAUUSD/runtime",
        headers=auth_headers,
        json={"config_hash": champion.config_hash, "healthy": False},
    )

    assert runtime.status_code == 200
    assert runtime.json()["action"] == "DEFENSIVE"
    assert runtime.json()["state"] == "DEFENSIVE"
