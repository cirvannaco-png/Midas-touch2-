from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.database import async_session
from app.models import SignalOutcome
from tests.conftest import VALID_BUY_SIGNAL


def _read_outcome(client, signal_id):
    async def _read():
        async with async_session() as session:
            return await session.scalar(
                select(SignalOutcome).where(SignalOutcome.signal_id == signal_id)
            )

    assert client.portal is not None
    return client.portal.call(_read)


def test_ea_outcome_contract_persists_environment_lineage_and_costs(client, auth_headers):
    signal_id = "outcome-contract-persist-1"
    signal_time = "2026-10-11T10:00:00+00:00"
    decision_time = "2026-10-11T10:00:01+00:00"
    execution_time = "2026-10-11T10:00:02+00:00"
    outcome_time = "2026-10-11T10:15:00+00:00"

    # This contract test needs the persisted source signal, not asynchronous
    # Telegram delivery. Suppress broadcast so the outbox worker cannot race
    # SQLite cleanup during fixture teardown.
    with patch(
        "app.routes.get_signal_broadcast_controls",
        new=AsyncMock(return_value=(True, set())),
    ):
        signal_response = client.post(
            "/signal",
            json={
                **VALID_BUY_SIGNAL,
                "signal_id": signal_id,
                "signal_time": signal_time,
                "decision_time": decision_time,
                "environment_key": "TRENDING|NORMAL|L2|LONDON",
            },
            headers=auth_headers,
        )
    assert signal_response.status_code == 200
    fingerprint = signal_response.json()["decision_fingerprint"]

    payload = {
        "signal_id": signal_id,
        "symbol": "EURUSD",
        "direction": "BUY",
        "outcome": "win",
        "realized_r": 0.85,
        "mfe_r": 1.25,
        "mae_r": 0.15,
        "bars_held": 9,
        "bars_to_fill": 1,
        "filled": True,
        "regime": "REGIME_TRENDING",
        "session": "SESSION_LONDON",
        "sweep_grade": "SWEEP_GRADE_A",
        "htf_ob_aligned": True,
        "weight_version": "weights-v4",
        "strategy": "STRATEGY_SMC",
        "resolution": "FinalTP_Hit",
        "exit_reason": "FinalTP_Hit",
        "commission_cost": 3.5,
        # Spread and slippage are deliberately unknown, not falsely set to zero.
        "spread_cost": None,
        "slippage_cost": None,
        # Signed broker cashflows must permit negative debits.
        "commission_cashflow": -3.5,
        "swap_cashflow": -0.75,
        "broker_fee_cashflow": -0.2,
        "decision_fingerprint": fingerprint,
        "signal_time": signal_time,
        "decision_time": decision_time,
        "execution_time": execution_time,
        "outcome_time": outcome_time,
        "environment_key": "TRENDING|NORMAL|L2|LONDON",
        "environment": {"atr_regime": "NORMAL", "spread_points": 12.0},
        "confidence_at_signal": 82.0,
        "confidence_decayed": 74.0,
        "decay_bars": 3,
    }
    response = client.post("/outcome", json=payload, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["signal_id"] == signal_id

    row = _read_outcome(client, signal_id)
    assert row is not None
    assert row.decision_fingerprint == fingerprint
    assert row.original_decision_fingerprint is None
    assert row.parity_status == "FINGERPRINT_MISSING"
    assert row.signal_time is not None
    assert row.decision_time is not None
    assert row.execution_time is not None
    assert row.outcome_time is not None
    assert row.environment_key == payload["environment_key"]
    assert row.environment == payload["environment"]
    assert row.resolution == "FinalTP_Hit"
    assert row.exit_reason == "FinalTP_Hit"
    assert row.commission_cost == 3.5
    assert row.spread_cost is None
    assert row.slippage_cost is None
    assert row.commission_cashflow == -3.5
    assert row.swap_cashflow == -0.75
    assert row.broker_fee_cashflow == -0.2


def test_signed_cashflows_are_accepted_but_negative_cost_magnitudes_are_rejected(client, auth_headers):
    accepted = client.post(
        "/outcome",
        headers=auth_headers,
        json={
            "signal_id": "outcome-signed-cashflows-accepted",
            "symbol": "EURUSD",
            "direction": "SELL",
            "outcome": "loss",
            "filled": True,
            "commission_cost": 1.25,
            "commission_cashflow": -1.25,
            "swap_cashflow": -0.4,
            "broker_fee_cashflow": -0.1,
        },
    )
    assert accepted.status_code == 200, accepted.text
    row = _read_outcome(client, "outcome-signed-cashflows-accepted")
    assert row is not None
    assert row.commission_cashflow == -1.25
    assert row.swap_cashflow == -0.4
    assert row.broker_fee_cashflow == -0.1

    rejected = client.post(
        "/outcome",
        headers=auth_headers,
        json={
            "signal_id": "outcome-negative-cost-rejected",
            "symbol": "EURUSD",
            "direction": "SELL",
            "outcome": "loss",
            "filled": True,
            "commission_cost": -1.25,
            "commission_cashflow": -1.25,
            "swap_cashflow": -0.4,
            "broker_fee_cashflow": -0.1,
        },
    )
    assert rejected.status_code == 422


def test_only_one_post_outcome_route_is_registered():
    from app.main import app
    from app.routes import router

    matching = [
        route
        for route in router.routes
        if getattr(route, "path", None) == "/outcome"
        and "POST" in getattr(route, "methods", set())
    ]
    assert len(matching) == 1
    assert app.openapi()["paths"]["/outcome"]["post"]


def test_outcome_fingerprint_mismatch_remains_visible_and_rejected(client, auth_headers):
    signal_id = "outcome-parity-mismatch-1"
    signal_response = client.post(
        "/signal",
        json={**VALID_BUY_SIGNAL, "signal_id": signal_id, "decision_fingerprint": "B" * 64},
        headers=auth_headers,
    )
    # The deliberately false claimed fingerprint is retained as a parity audit row.
    assert signal_response.status_code == 409

    response = client.post(
        "/outcome",
        headers=auth_headers,
        json={
            "signal_id": signal_id,
            "symbol": "EURUSD",
            "direction": "BUY",
            "outcome": "win",
            "filled": True,
            "decision_fingerprint": "A" * 64,
            "commission_cost": 0.0,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PARITY_MISMATCH"
    row = _read_outcome(client, signal_id)
    assert row is not None
    assert row.parity_status == "PARITY_MISMATCH"
