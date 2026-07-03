from functools import lru_cache
from decimal import Decimal

from pydantic import AliasChoices, Field, field_validator
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
    binance_market_data_base_url: str = Field(
        default="https://data-api.binance.vision",
        validation_alias=AliasChoices("BINANCE_MARKET_DATA_BASE_URL"),
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
    paper_initial_balance: Decimal = Field(
        default=Decimal("10000.00"),
        validation_alias=AliasChoices("PAPER_INITIAL_BALANCE", "SIMULATION_STARTING_CASH"),
    )
    simulation_fee_bps: Decimal = Field(
        default=Decimal("10"),
        validation_alias=AliasChoices("SIMULATION_FEE_BPS"),
    )
    simulation_slippage_bps: Decimal = Field(
        default=Decimal("5"),
        validation_alias=AliasChoices("SIMULATION_SLIPPAGE_BPS"),
    )
    paper_trading_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("PAPER_TRADING_ENABLED"),
    )
    binance_testnet_broker_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("BINANCE_TESTNET_BROKER_ENABLED"),
    )
    binance_testnet_order_submission_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("BINANCE_TESTNET_ORDER_SUBMISSION_ENABLED"),
    )
    binance_testnet_base_url: str = Field(
        default="https://testnet.binance.vision",
        validation_alias=AliasChoices("BINANCE_TESTNET_BASE_URL"),
    )
    binance_testnet_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        validation_alias=AliasChoices("BINANCE_TESTNET_TIMEOUT_SECONDS"),
    )
    binance_testnet_recv_window: int = Field(
        default=5000,
        gt=0,
        validation_alias=AliasChoices("BINANCE_TESTNET_RECV_WINDOW"),
    )
    binance_testnet_exchange_info_ttl_seconds: float = Field(
        default=300.0,
        gt=0,
        validation_alias=AliasChoices("BINANCE_TESTNET_EXCHANGE_INFO_TTL_SECONDS"),
    )
    binance_testnet_dry_run_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("BINANCE_TESTNET_DRY_RUN_ENABLED"),
    )
    binance_testnet_reconciliation_initial_delay_seconds: int = Field(
        default=300,
        gt=0,
        validation_alias=AliasChoices("BINANCE_TESTNET_RECONCILIATION_INITIAL_DELAY_SECONDS"),
    )
    binance_testnet_reconciliation_lease_seconds: int = Field(
        default=60,
        gt=0,
        validation_alias=AliasChoices("BINANCE_TESTNET_RECONCILIATION_LEASE_SECONDS"),
    )
    binance_testnet_reconciliation_retry_delay_seconds: int = Field(
        default=300,
        gt=0,
        validation_alias=AliasChoices("BINANCE_TESTNET_RECONCILIATION_RETRY_DELAY_SECONDS"),
    )
    binance_testnet_reconciliation_max_automatic_attempts: int = Field(
        default=5,
        gt=0,
        validation_alias=AliasChoices("BINANCE_TESTNET_RECONCILIATION_MAX_AUTOMATIC_ATTEMPTS"),
    )
    binance_testnet_reconciliation_batch_size: int = Field(
        default=10,
        gt=0,
        le=100,
        validation_alias=AliasChoices("BINANCE_TESTNET_RECONCILIATION_BATCH_SIZE"),
    )
    binance_testnet_reconciliation_worker_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("BINANCE_TESTNET_RECONCILIATION_WORKER_ENABLED"),
    )
    binance_testnet_reconciliation_worker_poll_interval_seconds: int = Field(
        default=30,
        gt=0,
        le=3600,
        validation_alias=AliasChoices("BINANCE_TESTNET_RECONCILIATION_WORKER_POLL_INTERVAL_SECONDS"),
    )
    binance_testnet_reconciliation_worker_heartbeat_stale_after_seconds: int = Field(
        default=120,
        gt=0,
        le=86400,
        validation_alias=AliasChoices("BINANCE_TESTNET_RECONCILIATION_WORKER_HEARTBEAT_STALE_AFTER_SECONDS"),
    )
    binance_testnet_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BINANCE_TESTNET_API_KEY"),
    )
    binance_testnet_api_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BINANCE_TESTNET_API_SECRET"),
    )
    execution_global_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("EXECUTION_GLOBAL_ENABLED"),
    )
    execution_live_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("EXECUTION_LIVE_ENABLED"),
    )
    execution_max_order_notional: Decimal | None = Field(
        default=None,
        validation_alias=AliasChoices("EXECUTION_MAX_ORDER_NOTIONAL"),
    )
    execution_max_daily_order_count: int | None = Field(
        default=None,
        validation_alias=AliasChoices("EXECUTION_MAX_DAILY_ORDER_COUNT"),
    )
    execution_max_daily_loss: Decimal | None = Field(
        default=None,
        validation_alias=AliasChoices("EXECUTION_MAX_DAILY_LOSS"),
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

    @field_validator("paper_initial_balance")
    @classmethod
    def validate_paper_initial_balance(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= Decimal("0"):
            raise ValueError("PAPER_INITIAL_BALANCE must be a positive decimal")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
