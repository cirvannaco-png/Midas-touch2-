import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.execution_ledger import execution_ledger_health
from app.database import Base
from app.models import (
    ExecutionLedger,
    ExecutionPositionModification,
    PortfolioReservation,
)


def test_execution_ledger_health_reports_schema_ready(client, auth_headers):
    response = client.get("/execution-ledger/health", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "online"
    assert body["database"] == "connected"
    assert body["execution_ledger"] == "ready"
    assert body["ledger_schema"] == "ready"


@pytest.mark.asyncio
async def test_execution_ledger_health_fails_when_required_table_is_missing():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    required_but_present_tables = [
        ExecutionLedger.__table__,
        PortfolioReservation.__table__,
        ExecutionPositionModification.__table__,
    ]

    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(
                    sync,
                    tables=required_but_present_tables,
                )
            )

        factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with factory() as session:
            with pytest.raises(HTTPException) as raised:
                await execution_ledger_health(session=session, _auth=True)

        assert raised.value.status_code == 503
        assert raised.value.detail == "execution ledger database/schema unavailable"
    finally:
        await engine.dispose()
