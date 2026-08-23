"""
Application configuration.

All values are read from environment variables (typically via a local .env
file — see .env.example). Nothing here is hardcoded.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    encryption_key: str | None = None
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"

    # If DATABASE_URL is provided directly, it wins. Otherwise we build it
    # from the individual POSTGRES_* pieces — useful when different team
    # members run Postgres with different host/port setups locally.
    database_url: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "campusflow"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    # JWT auth. jwt_secret has no safe default on purpose — set it via .env
    # (or the environment) in every deployment; do not commit a real value.
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Payment provider webhook. Provider-neutral HMAC-SHA256 shared secret,
    # same "no safe default in real deployments" convention as jwt_secret --
    # set a real value via .env, never commit one. The dev-only default lets
    # local/test runs sign requests without needing real provider credentials.
    payment_webhook_secret: str = "dev-only-insecure-webhook-secret-change-me"

    # Redis Streams event bus configuration. Defaults target a local
    # docker-compose/dev Redis instance -- override via env vars (see
    # .env.example) for staging/prod.
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_name: str = "campusflow.events"
    redis_consumer_group: str = "campusflow-automation"
    redis_consumer_name: str = "automation-worker-1"

    # Notification Service (Stage 4). "mock" (default) never touches the
    # network -- the whole automation chain runs with zero credentials.
    # "live" switches to real SMTP / SMS-webhook providers and requires
    # their respective config below to be set (see app/notifications).
    notification_provider_mode: str = "mock"

    # SMTP (real email provider). Only required when
    # NOTIFICATION_PROVIDER_MODE=live.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True

    # SMS (real provider, generic HTTP webhook). Only required when
    # NOTIFICATION_PROVIDER_MODE=live. Point this at whatever SMS
    # gateway the deployment actually uses.
    sms_webhook_url: str | None = None
    sms_api_key: str | None = None
    sms_from_number: str | None = None

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
