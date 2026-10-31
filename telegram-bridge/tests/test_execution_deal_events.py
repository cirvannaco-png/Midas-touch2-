from __future__ import annotations

import json


def _deal_payload() -> dict:
    return {
        "portfolio_key": "SelectedBroker-Demo:123456:987654321",
        "request_id": "brokerpos:SelectedBroker-Demo:123456:987654321:position-7001",
        "broker_deal_id": "7001",
        "broker_order_id": "6001",
        "broker_position_id": "5001",
        "symbol": "EURUSD",
        "entry_type": "IN",
        "deal_type": "BUY",
        "direction": "BUY",
        "volume": 1.0,
        "price": 1.1000,
        "profit_cashflow": 0.0,
        "commission_cashflow": -2.5,
        "swap_cashflow": 0.0,
        "fee_cashflow": 0.0,
        "cashflows_known": True,
        "position_open": True,
        "remaining_volume": 1.0,
        "risk_r": 1.2,
        "volatility": 0.7,
        "factors": {"eur": 1.0},
        "evidence_ref": "mt5-deal:7001",
    }


def test_deal_event_ingestion_is_idempotent_and_refreshes_position_snapshot(client):
    headers = {
        "X-API-Key": "test-secret-key",
        "X-MT5-Execution-Key": "test-mt5-execution-key-0123456789",
    }
    url = "/execution-ledger/deal-event"
    payload = _deal_payload()

    first = client.post(url, json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["stored"] is True
    assert first.json()["duplicate"] is False
    assert first.json()["reconciled"] is True
    assert first.json()["portfolio_heat_r"] == 1.2

    # The immutable broker deal is identical, but the latest broker snapshot
    # reflects a partial close and lower remaining stop-risk.
    replay = dict(payload)
    replay.update(
        {
            "remaining_volume": 0.4,
            "risk_r": 0.6,
            "evidence_ref": "mt5-restart-snapshot:5001",
        }
    )
    second = client.post(url, json=replay, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    assert second.json()["portfolio_heat_r"] == 0.6


def test_partial_and_full_close_deal_replays_do_not_duplicate_deals(client):
    headers = {
        "X-API-Key": "test-secret-key",
        "X-MT5-Execution-Key": "test-mt5-execution-key-0123456789",
    }
    url = "/execution-ledger/deal-event"
    opened = client.post(url, json=_deal_payload(), headers=headers)
    assert opened.status_code == 200, opened.text

    partial = _deal_payload()
    partial.update(
        {
            "broker_deal_id": "7002",
            "broker_order_id": "6002",
            "entry_type": "OUT",
            "deal_type": "SELL",
            "volume": 0.6,
            "price": 1.1020,
            "profit_cashflow": 12.0,
            "commission_cashflow": -1.5,
            "swap_cashflow": -0.1,
            "fee_cashflow": 0.0,
            "position_open": True,
            "remaining_volume": 0.4,
            "risk_r": 0.6,
            "evidence_ref": "mt5-deal:7002",
        }
    )
    partial_first = client.post(url, json=partial, headers=headers)
    assert partial_first.status_code == 200, partial_first.text
    assert partial_first.json()["duplicate"] is False
    assert partial_first.json()["portfolio_heat_r"] == 0.6

    full_close = dict(partial)
    full_close.update(
        {
            "broker_deal_id": "7003",
            "broker_order_id": "6003",
            "volume": 0.4,
            "price": 1.1030,
            "profit_cashflow": 8.0,
            "commission_cashflow": -1.0,
            "position_open": False,
            "remaining_volume": 0.0,
            "risk_r": 0.0,
            "evidence_ref": "mt5-deal:7003",
        }
    )
    closed = client.post(url, json=full_close, headers=headers)
    assert closed.status_code == 200, closed.text
    assert closed.json()["reconciled"] is True
    assert closed.json()["portfolio_heat_r"] is None

    repeated_close = client.post(url, json=full_close, headers=headers)
    assert repeated_close.status_code == 200, repeated_close.text
    assert repeated_close.json()["duplicate"] is True
    assert repeated_close.json()["reconciled"] is True


def test_deal_id_cannot_be_reused_with_conflicting_cashflow(client):
    headers = {
        "X-API-Key": "test-secret-key",
        "X-MT5-Execution-Key": "test-mt5-execution-key-0123456789",
    }
    url = "/execution-ledger/deal-event"
    payload = _deal_payload()
    first = client.post(url, json=payload, headers=headers)
    assert first.status_code == 200, first.text

    conflict = dict(payload)
    conflict["profit_cashflow"] = 99.0
    response = client.post(url, json=conflict, headers=headers)
    assert response.status_code == 409


def test_deal_event_rejects_non_finite_values(client):
    payload = _deal_payload()
    payload["profit_cashflow"] = float("nan")
    response = client.post(
        "/execution-ledger/deal-event",
        content=json.dumps(payload, allow_nan=True),
        headers={
            "X-API-Key": "test-secret-key",
            "X-MT5-Execution-Key": "test-mt5-execution-key-0123456789",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 422

def test_execution_ledger_health_verifies_api_key_and_database(client):
    unauthenticated = client.get(
        "/execution-ledger/health",
        headers={"X-API-Key": "wrong-key"},
    )
    assert unauthenticated.status_code == 401

    response = client.get(
        "/execution-ledger/health",
        headers={"X-API-Key": "test-secret-key"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "online",
        "database": "connected",
        "execution_ledger": "ready",
    }

def test_breakeven_protected_open_position_accepts_zero_remaining_stop_risk(client):
    payload = _deal_payload()
    payload.update(
        {
            "broker_deal_id": "7099",
            "broker_order_id": "6099",
            "entry_type": "OUT",
            "deal_type": "SELL",
            "position_open": True,
            "remaining_volume": 0.4,
            "risk_r": 0.0,
            "evidence_ref": "mt5-breakeven-stop:5001",
        }
    )
    response = client.post(
        "/execution-ledger/deal-event",
        json=payload,
        headers={
            "X-API-Key": "test-secret-key",
            "X-MT5-Execution-Key": "test-mt5-execution-key-0123456789",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["stored"] is True
    assert response.json()["reconciled"] is True
    assert response.json()["portfolio_heat_r"] == 0.0
