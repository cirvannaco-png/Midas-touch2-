from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.config import settings
from app.routes import verify_api_key
from scripts.render_sync_secrets import RenderSyncError, collect_secrets


def _base_env() -> dict[str, str]:
    return {
        "BOT_TOKEN": "123456:placeholder",
        "CHAT_ID": "-1000000000",
        "ADMIN_CHAT_ID": "777000777",
        "SECRET_KEY": "legacy-secret",
    }


def test_bridge_api_key_is_canonical_and_legacy_secret_is_fallback(monkeypatch):
    monkeypatch.setattr(settings, "BRIDGE_API_KEY", "workflow-bridge-secret")
    monkeypatch.setattr(settings, "SECRET_KEY", "legacy-secret")

    asyncio.run(verify_api_key("workflow-bridge-secret"))
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(verify_api_key("legacy-secret"))
    assert rejected.value.status_code == 401

    monkeypatch.setattr(settings, "BRIDGE_API_KEY", "")
    asyncio.run(verify_api_key("legacy-secret"))


def test_bridge_api_key_rejects_empty_effective_credential(monkeypatch):
    monkeypatch.setattr(settings, "BRIDGE_API_KEY", "")
    monkeypatch.setattr(settings, "SECRET_KEY", "   ")
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(verify_api_key("   "))
    assert rejected.value.status_code == 401


def test_render_secret_sync_aligns_both_names_to_workflow_key():
    env = {**_base_env(), "BRIDGE_API_KEY": "workflow-bridge-secret"}
    prepared = collect_secrets(env)
    assert prepared["BRIDGE_API_KEY"] == "workflow-bridge-secret"
    assert prepared["SECRET_KEY"] == "workflow-bridge-secret"


def test_render_secret_sync_keeps_legacy_fallback_for_existing_automation():
    prepared = collect_secrets(_base_env())
    assert prepared["BRIDGE_API_KEY"] == "legacy-secret"
    assert prepared["SECRET_KEY"] == "legacy-secret"



def test_render_secret_sync_accepts_workflow_key_without_legacy_alias():
    env = {
        "BOT_TOKEN": "123456:placeholder",
        "CHAT_ID": "-1000000000",
        "ADMIN_CHAT_ID": "777000777",
        "BRIDGE_API_KEY": "workflow-bridge-secret",
    }
    prepared = collect_secrets(env)
    assert prepared["BRIDGE_API_KEY"] == "workflow-bridge-secret"
    assert prepared["SECRET_KEY"] == "workflow-bridge-secret"


def test_render_secret_sync_requires_one_authentication_credential():
    env = {
        "BOT_TOKEN": "123456:placeholder",
        "CHAT_ID": "-1000000000",
        "ADMIN_CHAT_ID": "777000777",
    }
    with pytest.raises(RenderSyncError, match="BRIDGE_API_KEY"):
        collect_secrets(env)
