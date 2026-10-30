from __future__ import annotations

from uuid import uuid4


HEADERS = {"X-API-Key": "test-secret-key"}


def _modification_payload(direction: str = "BUY") -> dict:
    token = uuid4().hex[:16]
    is_buy = direction == "BUY"
    return {
        "portfolio_key": f"Exness-Demo:123456:{token}",
        "broker_position_id": str(500000 + int(token[:8], 16)),
        "symbol": "XAUUSD",
        "direction": direction,
        "volume": 0.01,
        "entry_price": 2300.0,
        "previous_sl": 2280.0 if is_buy else 2320.0,
        "applied_sl": 2290.0 if is_buy else 2310.0,
        "previous_tp": 2340.0 if is_buy else 2260.0,
        "applied_tp": 2340.0 if is_buy else 2260.0,
        "risk_r": 0.5,
        "volatility": 0.8,
        "evidence_ref": f"mt5-position-modification:{token}",
        "_request_id": f"position-mod-test-{token}",
    }


def _register_position(client, payload: dict) -> None:
    response = client.post(
        "/execution-ledger/sync-position",
        headers=HEADERS,
        json={
            "portfolio_key": payload["portfolio_key"],
            "request_id": payload["_request_id"],
            "broker_position_id": payload["broker_position_id"],
            "broker_order_id": f"order-{payload['broker_position_id']}",
            "broker_deal_id": f"deal-{payload['broker_position_id']}",
            "symbol": payload["symbol"],
            "direction": payload["direction"],
            "risk_r": 1.0,
            "volatility": payload["volatility"],
            "factors": {},
            "evidence_ref": f"mt5-position-open:{payload['broker_position_id']}",
        },
    )
    assert response.status_code == 200, response.text


def _request_payload(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if not key.startswith("_")}


def test_broker_position_modification_is_persisted_and_idempotent(client):
    payload = _modification_payload()
    _register_position(client, payload)
    request = _request_payload(payload)

    first = client.post("/execution-ledger/position-modification", headers=HEADERS, json=request)
    assert first.status_code == 200, first.text
    assert first.json()["updated"] is True
    assert first.json()["duplicate"] is False

    retry = client.post("/execution-ledger/position-modification", headers=HEADERS, json=request)
    assert retry.status_code == 200, retry.text
    assert retry.json()["duplicate"] is True


def test_position_modification_evidence_cannot_be_reused_for_different_state(client):
    payload = _modification_payload()
    _register_position(client, payload)
    request = _request_payload(payload)
    first = client.post("/execution-ledger/position-modification", headers=HEADERS, json=request)
    assert first.status_code == 200, first.text

    changed = {**request, "applied_sl": request["applied_sl"] + 1.0, "risk_r": 0.45}
    conflict = client.post("/execution-ledger/position-modification", headers=HEADERS, json=changed)

    assert conflict.status_code == 409
    assert "reused with different broker state" in conflict.json()["detail"]


def test_position_modification_requires_registered_broker_position(client):
    payload = _request_payload(_modification_payload())
    response = client.post(
        "/execution-ledger/position-modification",
        headers=HEADERS,
        json=payload,
    )
    assert response.status_code == 404
    assert "not registered" in response.json()["detail"]


def test_position_modification_endpoint_requires_bridge_authentication(client):
    payload = _request_payload(_modification_payload())
    response = client.post(
        "/execution-ledger/position-modification",
        headers={"X-API-Key": "wrong-key"},
        json=payload,
    )
    assert response.status_code == 401


def test_buy_position_modification_cannot_loosen_protective_stop(client):
    payload = _modification_payload("BUY")
    _register_position(client, payload)
    request = _request_payload(payload)
    request["applied_sl"] = request["previous_sl"] - 1.0

    response = client.post("/execution-ledger/position-modification", headers=HEADERS, json=request)

    assert response.status_code == 422
    assert "must not loosen the stop" in response.json()["detail"]


def test_sell_position_modification_cannot_loosen_protective_stop(client):
    payload = _modification_payload("SELL")
    _register_position(client, payload)
    request = _request_payload(payload)
    request["applied_sl"] = request["previous_sl"] + 1.0

    response = client.post("/execution-ledger/position-modification", headers=HEADERS, json=request)

    assert response.status_code == 422
    assert "must not loosen the stop" in response.json()["detail"]
