from __future__ import annotations


HEADERS = {"X-API-Key": "test-secret-key"}


def _register_position(client):
    response = client.post(
        "/execution-ledger/sync-position",
        headers=HEADERS,
        json={
            "portfolio_key": "Exness-Demo:123456:987654321",
            "request_id": "position-mod-test-1",
            "broker_position_id": "5001",
            "broker_order_id": "6001",
            "broker_deal_id": "7001",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "risk_r": 1.0,
            "volatility": 0.8,
            "factors": {},
            "evidence_ref": "mt5-position-open:5001",
        },
    )
    assert response.status_code == 200, response.text


def _modification_payload():
    return {
        "portfolio_key": "Exness-Demo:123456:987654321",
        "broker_position_id": "5001",
        "symbol": "XAUUSD",
        "direction": "BUY",
        "volume": 0.01,
        "entry_price": 2300.0,
        "previous_sl": 2280.0,
        "applied_sl": 2290.0,
        "previous_tp": 2340.0,
        "applied_tp": 2340.0,
        "risk_r": 0.5,
        "volatility": 0.8,
        "evidence_ref": "mt5-position-modification:5001:100:1",
    }


def test_broker_position_modification_is_persisted_and_idempotent(client):
    _register_position(client)
    payload = _modification_payload()

    first = client.post("/execution-ledger/position-modification", headers=HEADERS, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["updated"] is True
    assert first.json()["duplicate"] is False

    retry = client.post("/execution-ledger/position-modification", headers=HEADERS, json=payload)
    assert retry.status_code == 200, retry.text
    assert retry.json()["duplicate"] is True


def test_position_modification_evidence_cannot_be_reused_for_different_state(client):
    _register_position(client)
    payload = _modification_payload()
    first = client.post("/execution-ledger/position-modification", headers=HEADERS, json=payload)
    assert first.status_code == 200, first.text

    changed = {**payload, "applied_sl": 2291.0, "risk_r": 0.45}
    conflict = client.post("/execution-ledger/position-modification", headers=HEADERS, json=changed)

    assert conflict.status_code == 409
    assert "reused with different broker state" in conflict.json()["detail"]


def test_position_modification_requires_registered_broker_position(client):
    response = client.post(
        "/execution-ledger/position-modification",
        headers=HEADERS,
        json=_modification_payload(),
    )
    assert response.status_code == 404
    assert "not registered" in response.json()["detail"]


def test_position_modification_endpoint_requires_bridge_authentication(client):
    response = client.post(
        "/execution-ledger/position-modification",
        headers={"X-API-Key": "wrong-key"},
        json=_modification_payload(),
    )
    assert response.status_code == 401
