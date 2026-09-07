"""Telegram webhook boundary for Phase B.

This module documents the extraction seam only. The live endpoint remains in
``app.routes`` until it can be moved without changing Telegram's response,
secret-token validation, or update-processing behavior.
"""

import secrets

from fastapi import HTTPException

from app.config import settings


def validate_telegram_webhook_secret(token: str | None) -> None:
    """Preserve the existing fail-closed Telegram secret-token check."""
    if not secrets.compare_digest(token or "", settings.WEBHOOK_SECRET_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid secret token")


__all__ = ["validate_telegram_webhook_secret"]
