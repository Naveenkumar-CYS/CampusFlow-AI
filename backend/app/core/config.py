"""
Application configuration.

All values are read from environment variables (typically via a local .env
file — see .env.example). Nothing here is hardcoded.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
