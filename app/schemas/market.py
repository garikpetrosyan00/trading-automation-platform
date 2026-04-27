from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PositivePrice = Annotated[Decimal, Field(gt=0)]
NonNegativeQuantity = Annotated[Decimal, Field(ge=0)]


class MarketPriceUpdateRequest(BaseModel):
    symbol: str
    price: PositivePrice

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Symbol must not be empty")
        return normalized


class MarketSymbolRequest(BaseModel):
    symbol: str

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Symbol must not be empty")
        return normalized


class MarketPriceRead(BaseModel):
    symbol: str
    price: Decimal
    updated_at: datetime


class BinanceMarketPriceRead(MarketPriceRead):
    source: str


class BinanceMarketCandlesRequest(BaseModel):
    symbol: str
    timeframe: str
    limit: int = Field(default=100, ge=1, le=500)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Symbol must not be empty")
        return normalized

    @field_validator("timeframe")
    @classmethod
    def normalize_timeframe(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Timeframe must not be empty")
        return normalized


class MarketCandleBase(BaseModel):
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open_price: PositivePrice
    high_price: PositivePrice
    low_price: PositivePrice
    close_price: PositivePrice
    volume: NonNegativeQuantity = Decimal("0")
    source: str = "manual"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Symbol must not be empty")
        return normalized

    @field_validator("timeframe", "source")
    @classmethod
    def normalize_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_candle_shape(self) -> "MarketCandleBase":
        if self.close_time < self.open_time:
            raise ValueError("close_time must be greater than or equal to open_time")

        if self.high_price < max(self.open_price, self.close_price, self.low_price):
            raise ValueError("high_price must be greater than or equal to open_price, close_price, and low_price")

        if self.low_price > min(self.open_price, self.close_price, self.high_price):
            raise ValueError("low_price must be less than or equal to open_price, close_price, and high_price")

        return self


class MarketCandleCreate(MarketCandleBase):
    pass


class MarketCandleRead(MarketCandleBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BinanceMarketCandlesRead(BaseModel):
    symbol: str
    timeframe: str
    source: str
    requested_limit: int
    stored_count: int
    candles: list[MarketCandleRead]
