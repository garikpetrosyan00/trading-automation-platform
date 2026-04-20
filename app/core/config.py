from functools import lru_cache
from decimal import Decimal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Trading Automation Platform", validation_alias=AliasChoices("APP_NAME"))
    environment: str = Field(default="local", validation_alias=AliasChoices("APP_ENVIRONMENT"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("APP_DEBUG"))
    api_v1_prefix: str = Field(default="/api/v1", validation_alias=AliasChoices("APP_API_V1_PREFIX"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("APP_LOG_LEVEL"))
    market_data_enabled: bool = Field(default=True, validation_alias=AliasChoices("MARKET_DATA_ENABLED"))
    market_data_provider: str = Field(default="binance", validation_alias=AliasChoices("MARKET_DATA_PROVIDER"))
    market_data_symbol: str = Field(default="BTCUSDT", validation_alias=AliasChoices("MARKET_DATA_SYMBOL"))
    market_data_websocket_url: str = Field(
        default="wss://stream.binance.com:9443/ws",
        validation_alias=AliasChoices("MARKET_DATA_WEBSOCKET_URL"),
    )
    market_data_reconnect_delay_seconds: float = Field(
        default=2.0,
        validation_alias=AliasChoices("MARKET_DATA_RECONNECT_DELAY_SECONDS"),
    )
    market_data_include_raw_payload: bool = Field(
        default=False,
        validation_alias=AliasChoices("MARKET_DATA_INCLUDE_RAW_PAYLOAD"),
    )
    simulation_enabled: bool = Field(default=True, validation_alias=AliasChoices("SIMULATION_ENABLED"))
    simulation_base_currency: str = Field(default="USD", validation_alias=AliasChoices("SIMULATION_BASE_CURRENCY"))
    simulation_starting_cash: Decimal = Field(
        default=Decimal("1000.00"),
        validation_alias=AliasChoices("SIMULATION_STARTING_CASH"),
    )
    simulation_fee_bps: Decimal = Field(
        default=Decimal("10"),
        validation_alias=AliasChoices("SIMULATION_FEE_BPS"),
    )
    simulation_slippage_bps: Decimal = Field(
        default=Decimal("5"),
        validation_alias=AliasChoices("SIMULATION_SLIPPAGE_BPS"),
    )
    bot_runner_enabled: bool = Field(default=True, validation_alias=AliasChoices("BOT_RUNNER_ENABLED"))
    bot_runner_poll_interval_seconds: float = Field(
        default=2.0,
        validation_alias=AliasChoices("BOT_RUNNER_POLL_INTERVAL_SECONDS"),
    )

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
