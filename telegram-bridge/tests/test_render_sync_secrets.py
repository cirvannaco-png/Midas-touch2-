import importlib.util
import pathlib

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "render_sync_secrets",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "render_sync_secrets.py",
)
rss = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(rss)


BASE_ENV = {
    "BOT_TOKEN": "123456:abc",
    "CHAT_ID": "-1000000000",
    "ADMIN_CHAT_ID": "777000777",
    "SECRET_KEY": "s3cret",
}


def test_generated_token_is_telegram_compatible():
    for _ in range(50):
        token = rss.generate_webhook_secret_token()
        assert rss.TELEGRAM_SECRET_TOKEN_RE.fullmatch(token)


def test_missing_required_secret_raises():
    with pytest.raises(rss.RenderSyncError) as exc:
        rss.collect_secrets({"BOT_TOKEN": "x"})
    assert "CHAT_ID" in str(exc.value)


def test_webhook_token_generated_when_absent():
    values = rss.collect_secrets(dict(BASE_ENV))
    assert rss.TELEGRAM_SECRET_TOKEN_RE.fullmatch(values["WEBHOOK_SECRET_TOKEN"])


def test_supplied_webhook_token_is_preserved():
    env = {**BASE_ENV, "WEBHOOK_SECRET_TOKEN": "abc_DEF-123"}
    assert rss.collect_secrets(env)["WEBHOOK_SECRET_TOKEN"] == "abc_DEF-123"


@pytest.mark.parametrize("bad", ["has space", "plus+sign", "slash/", "pad==", "", "x" * 257])
def test_invalid_webhook_token_rejected(bad):
    env = {**BASE_ENV, "WEBHOOK_SECRET_TOKEN": bad}
    if bad == "":
        # empty falls back to generation, which must always be valid
        assert rss.TELEGRAM_SECRET_TOKEN_RE.fullmatch(rss.collect_secrets(env)["WEBHOOK_SECRET_TOKEN"])
        return
    with pytest.raises(rss.RenderSyncError):
        rss.collect_secrets(env)


def test_dry_run_makes_no_api_calls(monkeypatch, capsys):
    def boom(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("no HTTP call expected in --dry-run")

    monkeypatch.setattr(rss, "_request", boom)
    for k, v in BASE_ENV.items():
        monkeypatch.setenv(k, v)
    assert rss.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out
    assert BASE_ENV["SECRET_KEY"] not in out



def test_bridge_auth_sync_writes_only_the_canonical_bridge_aliases():
    values = rss.collect_bridge_auth({
        "BRIDGE_API_KEY": "canonical-key",
        "MT5_EXECUTION_API_KEY": "obsolete-unused-value",
    })
    assert values == {
        "SECRET_KEY": "canonical-key",
        "BRIDGE_API_KEY": "canonical-key",
    }


def test_bridge_auth_sync_rejects_conflicting_bridge_aliases_before_any_api_call():
    with pytest.raises(rss.RenderSyncError, match="differ"):
        rss.collect_bridge_auth(
            {"BRIDGE_API_KEY": "workflow-key", "SECRET_KEY": "different-render-key"}
        )


def test_bridge_auth_sync_requires_protected_key():
    with pytest.raises(rss.RenderSyncError, match="Missing BRIDGE_API_KEY"):
        rss.collect_bridge_auth({})


def test_render_env_sync_updates_only_requested_keys_and_deletes_legacy_key(monkeypatch):
    requests = []

    def fake_request(method, path, api_key, body=None):
        requests.append((method, path, body))
        if method == "GET":
            return [
                {"envVar": {"key": key}}
                for key in (*rss.REQUIRED_RUNTIME_KEYS, "SECRET_KEY", "UNRELATED_SETTING")
            ]
        return None

    monkeypatch.setattr(rss, "_request", fake_request)
    rss.put_env_vars(
        "srv-test",
        "render-api-key",
        {"SECRET_KEY": "canonical", "BRIDGE_API_KEY": "canonical"},
    )

    assert requests[0] == (
        "GET", "/services/srv-test/env-vars?limit=100", None
    )
    assert requests[1:3] == [
        ("PUT", "/services/srv-test/env-vars/BRIDGE_API_KEY", {"value": "canonical"}),
        ("PUT", "/services/srv-test/env-vars/SECRET_KEY", {"value": "canonical"}),
    ]
    assert requests[3] == (
        "DELETE", "/services/srv-test/env-vars/MT5_EXECUTION_API_KEY", None
    )
    assert not any(method == "PUT" and path.endswith("/env-vars") for method, path, _ in requests)


def test_render_env_sync_refuses_to_deploy_when_required_runtime_key_is_missing(monkeypatch):
    requests = []

    def fake_request(method, path, api_key, body=None):
        requests.append((method, path, body))
        if method == "GET":
            return [{"envVar": {"key": key}} for key in ("BOT_TOKEN", "CHAT_ID", "WEBHOOK_SECRET_TOKEN")]
        return None

    monkeypatch.setattr(rss, "_request", fake_request)
    with pytest.raises(rss.RenderSyncError, match="ADMIN_CHAT_ID"):
        rss.put_env_vars(
            "srv-test",
            "render-api-key",
            {"SECRET_KEY": "canonical", "BRIDGE_API_KEY": "canonical"},
        )
    assert len(requests) == 1
