from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Trading Automation Platform"
    environment: str = Field(default="local", validation_alias=AliasChoices("APP_ENVIRONMENT"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("APP_DEBUG"))
    api_v1_prefix: str = Field(default="/api/v1", validation_alias=AliasChoices("APP_API_V1_PREFIX"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("APP_LOG_LEVEL"))

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/trading_platform",
        description="SQLAlchemy database URL",
    )
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "trading_platform"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
