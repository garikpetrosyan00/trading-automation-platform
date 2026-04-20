from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MarketEventType(str, Enum):
    TICKER = "ticker"


class MarketDataProviderName(str, Enum):
    BINANCE = "binance"


class MarketEvent(BaseModel):
    provider: str
    symbol: str
    event_type: MarketEventType
    event_ts: datetime
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    price: Decimal | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: Decimal | None = None
    raw_payload: dict[str, Any] | None = None

    model_config = ConfigDict(use_enum_values=True)


class MarketDataStatus(BaseModel):
    running: bool
    enabled: bool
    provider: str
    symbol: str
    last_received_event_ts: datetime | None = None
    last_received_at: datetime | None = None
    received_event_count: int = 0


class MarketDataLatestResponse(BaseModel):
    symbol: str | None = None
    latest: MarketEvent | dict[str, MarketEvent]
