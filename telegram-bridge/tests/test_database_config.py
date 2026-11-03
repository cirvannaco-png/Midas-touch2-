from pathlib import Path

import pytest

from app.config import validate_database_url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://user:pass@localhost:5432/midas",
        "postgresql+asyncpg://user:pass@127.0.0.1:5432/midas",
        "postgresql+asyncpg://user:pass@[::1]:5432/midas",
    ],
)
def test_production_rejects_localhost_postgresql(url):
    with pytest.raises(ValueError, match="cannot use localhost or a loopback address"):
        validate_database_url(url, production=True)


def test_missing_database_url_fails_with_clear_error():
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        validate_database_url("", production=True)


def test_production_rejects_sqlite():
    with pytest.raises(ValueError, match="must use PostgreSQL"):
        validate_database_url("sqlite+aiosqlite:///./signals.db", production=True)



def test_malformed_database_url_fails_before_engine_creation():
    with pytest.raises(ValueError, match="DATABASE_URL is malformed"):
        validate_database_url(
            "postgresql+asyncpg://user:pass@db.internal:not-a-port/midas",
            production=True,
        )


def test_production_accepts_remote_postgresql_and_normalizes_scheme():
    url = validate_database_url(
        "postgresql://user:pass@db.internal:5432/midas",
        production=True,
    )
    assert url == "postgresql+asyncpg://user:pass@db.internal:5432/midas"


def test_local_development_can_explicitly_use_sqlite():
    assert validate_database_url(
        "sqlite+aiosqlite:///./signals.db",
        production=False,
    ) == "sqlite+aiosqlite:///./signals.db"


def test_docker_validates_settings_before_alembic_starts():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")
    validation = dockerfile.index("from app.config import settings")
    migrations = dockerfile.index("alembic upgrade head &&")
    assert validation < migrations
    assert "DATABASE_URL is required" in dockerfile
