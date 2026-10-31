import pytest
from pydantic import ValidationError

from app.config import Settings


def _settings(**overrides):
    values = {
        "BOT_TOKEN": "123456:test-token",
        "CHAT_ID": "-1000000000",
        "ADMIN_CHAT_ID": "777000777",
        "SECRET_KEY": "canonical-bridge-key",
        "WEBHOOK_SECRET_TOKEN": "test-webhook-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_legacy_secret_key_is_the_bridge_authentication_fallback():
    settings = _settings()
    assert settings.bridge_api_key == "canonical-bridge-key"


def test_explicit_bridge_api_key_must_match_render_secret_key():
    settings = _settings(BRIDGE_API_KEY="canonical-bridge-key")
    assert settings.bridge_api_key == settings.SECRET_KEY


def test_mismatched_authentication_alias_fails_settings_validation():
    with pytest.raises(ValidationError, match="BRIDGE_API_KEY and SECRET_KEY must be identical"):
        _settings(BRIDGE_API_KEY="different-key")



def test_single_bridge_credential_requires_no_mt5_specific_setting():
    settings = _settings()
    assert settings.bridge_api_key == "canonical-bridge-key"
    assert not hasattr(settings, "MT5_EXECUTION_API_KEY")
