import re

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "1.6.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    CHAT_ID: str
    ADMIN_CHAT_ID: str
    ADMIN_USER_ID: str = ""
    GROUP_CHAT_ID: str = ""
    SECRET_KEY: str
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/medis_touch"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    LOG_LEVEL: str = "INFO"
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_MAX_REQUESTS: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    MAX_REQUEST_BODY_SIZE: int = 10 * 1024
    PENDING_STALE_SECONDS: int = 120
    ALLOWED_ORIGINS: str = ""
    TELEGRAM_TIMEOUT_SECONDS: float = 8.0
    TELEGRAM_MAX_RETRIES: int = 3
    TELEGRAM_RETRY_MAX_WAIT_SECONDS: float = 4.0

    # Recalibration promotion policy is deliberately opt-in. If any required
    # threshold is absent, the lifecycle stays HOLD rather than inventing a
    # live trading policy from code defaults.
    RECALIBRATION_MIN_SCORE_DELTA: float | None = None
    RECALIBRATION_MAX_OOS_DEGRADATION: float | None = None
    RECALIBRATION_MAX_PARAMETER_DEGRADATION: float | None = None
    RECALIBRATION_MAX_P_VALUE: float | None = None

    SUBSCRIPTION_PROVIDER_TOKEN: str = ""
    SUBSCRIPTION_CURRENCY: str = "XTR"
    SUBSCRIPTION_PRICE_AMOUNT: int = 500
    SUBSCRIPTION_PERIOD_DAYS: int = 30
    SUBSCRIPTION_GRACE_PERIOD_DAYS: int = 3
    SUBSCRIPTION_WARNING_HOURS_BEFORE_EXPIRY: int = 24
    COPY_TRADING_CONFIRM_TTL_SECONDS: int = 120
    COPY_FEED_MAX_SIGNALS: int = 20

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def _noop(cls, v: str) -> str:
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        if not self.ALLOWED_ORIGINS.strip():
            return []
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    WEBHOOK_SECRET_TOKEN: str

    @field_validator("WEBHOOK_SECRET_TOKEN")
    @classmethod
    def _validate_webhook_secret_token(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", v):
            raise ValueError(
                "WEBHOOK_SECRET_TOKEN must match ^[A-Za-z0-9_-]{1,256}$ "
                "(Telegram's requirement for secret_token). Regenerate with: "
                "openssl rand -hex 32"
            )
        return v

    RENDER_EXTERNAL_URL: str = ""
    WEBHOOK_URL: str = ""
    WEBHOOK_PATH: str = "/telegram/webhook"

    @property
    def webhook_url(self) -> str:
        base = (self.WEBHOOK_URL or self.RENDER_EXTERNAL_URL).rstrip("/")
        path = self.WEBHOOK_PATH.strip("/")
        if not base:
            return f"/{path}"
        if base.endswith(f"/{path}"):
            return base
        return f"{base}/{path}"

    @property
    def authorized_chat_id(self) -> str:
        return self.ADMIN_CHAT_ID

    @property
    def authorized_user_id(self) -> str:
        return (self.ADMIN_USER_ID or self.ADMIN_CHAT_ID).strip()

    @property
    def broadcast_chat_ids(self) -> list[str]:
        ids: list[str] = []
        for cid in (self.CHAT_ID, self.GROUP_CHAT_ID):
            cid = (cid or "").strip()
            if cid and cid not in ids:
                ids.append(cid)
        return ids


settings = Settings()
