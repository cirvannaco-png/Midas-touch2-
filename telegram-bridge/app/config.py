import ipaddress
import os
import re
import secrets

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

APP_VERSION = "1.6.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    CHAT_ID: str
    ADMIN_CHAT_ID: str
    ADMIN_USER_ID: str = ""
    GROUP_CHAT_ID: str = ""
    SECRET_KEY: str
    BRIDGE_API_KEY: str | None = None

    @model_validator(mode="after")
    def _validate_bridge_api_key_alias(self):
        """One credential must authenticate GitHub maintenance and bridge routes."""
        if self.BRIDGE_API_KEY and not secrets.compare_digest(self.SECRET_KEY, self.BRIDGE_API_KEY):
            raise ValueError("BRIDGE_API_KEY and SECRET_KEY must be identical when both are configured")
        return self

    @property
    def bridge_api_key(self) -> str:
        return self.BRIDGE_API_KEY or self.SECRET_KEY
    # No implicit database target: production must receive the existing
    # Render PostgreSQL connection string; local development opts in explicitly.
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        return validate_database_url(value, production=_is_production_runtime())

    LOG_LEVEL: str = "INFO"
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_MAX_REQUESTS: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    MAX_REQUEST_BODY_SIZE: int = 10 * 1024
    # Dedicated, bounded allowance for authenticated historical Tester evidence.
    MAX_BACKTEST_EVIDENCE_BODY_SIZE: int = 5 * 1024 * 1024
    PENDING_STALE_SECONDS: int = 120
    ALLOWED_ORIGINS: str = ""
    TELEGRAM_TIMEOUT_SECONDS: float = 8.0
    TELEGRAM_MAX_RETRIES: int = 3
    TELEGRAM_RETRY_MAX_WAIT_SECONDS: float = 4.0
    # Roll out strict EA/backend fingerprint enforcement only after the
    # fingerprint-capable EA build has been compiled and deployed.
    REQUIRE_DECISION_FINGERPRINT: bool = False
    # Read-only Render benchmark endpoint. Disabled by default so production
    # services cannot accidentally expose the benchmark route.
    BENCHMARK_ENABLED: bool = False
    BENCHMARK_API_KEY: str = ""

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



def _is_production_runtime() -> bool:
    """Detect Render or an explicitly production-configured process."""
    return (
        os.getenv("RENDER", "").lower() == "true"
        or bool(os.getenv("RENDER_EXTERNAL_URL"))
        or os.getenv("APP_ENV", "").lower() == "production"
    )


def validate_database_url(value: str, *, production: bool = False) -> str:
    """Normalize and validate a DB URL before app/Alembic engine creation."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("DATABASE_URL is required and must not be empty")

    value = value.strip()
    if value.startswith("postgres://"):
        value = "postgresql+asyncpg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+asyncpg://" + value[len("postgresql://"):]

    try:
        parsed = make_url(value)
        host = parsed.host
    except (ArgumentError, TypeError, ValueError) as exc:
        raise ValueError("DATABASE_URL is malformed; provide a valid database URL") from exc

    if parsed.drivername in {"postgresql+asyncpg", "postgresql"}:
        if not host:
            raise ValueError("DATABASE_URL PostgreSQL URL must include a database host")
        if production:
            normalized_host = host.lower().rstrip(".")
            is_loopback = normalized_host in {"localhost", "localhost.localdomain"} or normalized_host.endswith(".localhost")
            try:
                is_loopback = is_loopback or ipaddress.ip_address(host).is_loopback
            except ValueError:
                pass
            if is_loopback:
                raise ValueError(
                    "Production DATABASE_URL cannot use localhost or a loopback address; "
                    "configure the existing Render PostgreSQL Internal Database URL."
                )
    elif parsed.drivername == "sqlite+aiosqlite":
        if production:
            raise ValueError("Production DATABASE_URL must use PostgreSQL, not SQLite")
    else:
        raise ValueError(
            "DATABASE_URL must use postgresql+asyncpg:// or sqlite+aiosqlite://"
        )

    return value


settings = Settings()
