from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

PositivePrice = Annotated[Decimal, Field(gt=0)]


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


class MarketPriceRead(BaseModel):
    symbol: str
    price: Decimal
    updated_at: datetime
