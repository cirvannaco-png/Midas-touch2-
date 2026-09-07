"""Medis Touch Telegram bridge application package."""

# Register recalibration ORM metadata alongside the existing models.
from app import config_evaluation_model as _config_evaluation_model  # noqa: F401
from app import config_registry_model as _config_registry_model  # noqa: F401
