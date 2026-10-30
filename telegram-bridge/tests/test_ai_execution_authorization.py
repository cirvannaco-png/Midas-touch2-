from app.config import settings

DEMO_PORTFOLIO = "DEMO:EXNESS:123456:magic-77"


def _reserve_demo_intent(client, auth_headers, request_id="ai-open-1"):
    response = client.post(
        "/execution-ledger/reserve",
        headers=auth_headers,
        json={
            "portfolio_key": DEMO_PORTFOLIO,
            "request_id": request_id,
            "signal_id": "ai-signal-1",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "risk_r": 0.5,
            "volatility": 0.4,
            "factors": {"gold": 1.0},
        },
    )
    assert response.status_code == 200, response.text
    return request_id


def _ai_request(request_id="ai-open-1", **overrides):
    body = {
        "portfolio_key": DEMO_PORTFOLIO,
        "request_id": request_id,
        "actor": "EXTERNAL_AI",
        "operation": "OPEN",
        "authorization_id": "ai-auth-1",
        "operator_approval_ref": "operator-approval:demo-001",
        "demo_validation_ref": "demo-forward-test:2026-10",
    }
    body.update(overrides)
    return body


def test_external_ai_authorization_is_disabled_by_default(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "AI_DEMO_EXECUTION_ENABLED", False)
    monkeypatch.setattr(settings, "AI_DEMO_PORTFOLIO_ALLOWLIST", DEMO_PORTFOLIO)

    response = client.post(
        "/execution-ledger/authorize-ai",
        headers=auth_headers,
        json=_ai_request(),
    )

    assert response.status_code == 403
    assert "disabled" in response.json()["detail"]


def test_external_ai_can_authorize_only_allowlisted_demo_ledger_intent(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "AI_DEMO_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "AI_DEMO_PORTFOLIO_ALLOWLIST", DEMO_PORTFOLIO)
    _reserve_demo_intent(client, auth_headers)

    response = client.post(
        "/execution-ledger/authorize-ai",
        headers=auth_headers,
        json=_ai_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authorized"] is True
    assert body["broker_execution_allowed"] is False
    assert "native EA ledger reservation" in body["execution_boundary"]


def test_external_ai_cannot_authorize_live_or_unallowlisted_portfolios(
    client, auth_headers, monkeypatch
):
    live_portfolio = "EXNESS-LIVE:123456:magic-77"
    monkeypatch.setattr(settings, "AI_DEMO_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "AI_DEMO_PORTFOLIO_ALLOWLIST", live_portfolio)

    response = client.post(
        "/execution-ledger/authorize-ai",
        headers=auth_headers,
        json=_ai_request(portfolio_key=live_portfolio),
    )

    assert response.status_code == 403
    assert "DEMO" in response.json()["detail"]


def test_ai_modify_requires_broker_confirmed_filled_position(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "AI_DEMO_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "AI_DEMO_PORTFOLIO_ALLOWLIST", DEMO_PORTFOLIO)
    _reserve_demo_intent(client, auth_headers, request_id="ai-modify-pending")

    response = client.post(
        "/execution-ledger/authorize-ai",
        headers=auth_headers,
        json=_ai_request(
            request_id="ai-modify-pending",
            operation="MODIFY",
            broker_position_id="position-not-filled",
        ),
    )

    assert response.status_code == 409
    assert "broker-confirmed FILLED position" in response.json()["detail"]


def test_ai_authorization_requires_both_operator_and_demo_evidence(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "AI_DEMO_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "AI_DEMO_PORTFOLIO_ALLOWLIST", DEMO_PORTFOLIO)
    _reserve_demo_intent(client, auth_headers, request_id="ai-evidence-missing")

    response = client.post(
        "/execution-ledger/authorize-ai",
        headers=auth_headers,
        json=_ai_request(
            request_id="ai-evidence-missing",
            authorization_id="ai-auth-no-evidence",
            demo_validation_ref="",
        ),
    )

    assert response.status_code == 422


def test_position_modification_endpoint_reconciles_actual_broker_position(
    client, auth_headers
):
    sync = client.post(
        "/execution-ledger/sync-position",
        headers=auth_headers,
        json={
            "portfolio_key": DEMO_PORTFOLIO,
            "request_id": "position-mod-api-1",
            "broker_position_id": "9001",
            "broker_order_id": "8001",
            "broker_deal_id": "7001",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "risk_r": 0.8,
            "volatility": 0.5,
            "factors": {},
            "evidence_ref": "mt5-position-snapshot:9001",
        },
    )
    assert sync.status_code == 200, sync.text

    body = {
        "portfolio_key": DEMO_PORTFOLIO,
        "broker_position_id": "9001",
        "symbol": "XAUUSD",
        "direction": "BUY",
        "modification_id": "mt5-posmod:9001:tick-1",
        "old_stop_loss": 2300.0,
        "new_stop_loss": 2310.0,
        "old_take_profit": 2350.0,
        "new_take_profit": 2360.0,
        "risk_r": 0.4,
        "volatility": 0.4,
        "evidence_ref": "mt5-position-modification:9001:tick-1",
    }
    first = client.post(
        "/execution-ledger/position-modification",
        headers=auth_headers,
        json=body,
    )
    second = client.post(
        "/execution-ledger/position-modification",
        headers=auth_headers,
        json=body,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["reconciled"] is True


def test_position_modification_endpoint_rejects_stop_loosening(client, auth_headers):
    sync = client.post(
        "/execution-ledger/sync-position",
        headers=auth_headers,
        json={
            "portfolio_key": DEMO_PORTFOLIO,
            "request_id": "position-mod-api-2",
            "broker_position_id": "9002",
            "broker_order_id": "8002",
            "broker_deal_id": "7002",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "risk_r": 0.8,
            "volatility": 0.5,
            "factors": {},
            "evidence_ref": "mt5-position-snapshot:9002",
        },
    )
    assert sync.status_code == 200, sync.text

    response = client.post(
        "/execution-ledger/position-modification",
        headers=auth_headers,
        json={
            "portfolio_key": DEMO_PORTFOLIO,
            "broker_position_id": "9002",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "modification_id": "mt5-posmod:9002:loosen",
            "old_stop_loss": 2310.0,
            "new_stop_loss": 2305.0,
            "old_take_profit": 2350.0,
            "new_take_profit": 2360.0,
            "risk_r": 0.7,
            "volatility": 0.4,
            "evidence_ref": "mt5-position-modification:9002:loosen",
        },
    )

    assert response.status_code == 422
    assert "cannot be loosened" in response.json()["detail"]
