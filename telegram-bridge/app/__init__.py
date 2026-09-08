"""Medis Touch Telegram bridge application package."""

# Register ORM metadata alongside the existing models.
from app import config_registry_model as _config_registry_model  # noqa: F401
from app import config_evaluation_model as _config_evaluation_model  # noqa: F401
from app import config_sync_state_model as _config_sync_state_model  # noqa: F401
