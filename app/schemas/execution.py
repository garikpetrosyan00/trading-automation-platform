from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PositiveDecimal = Annotated[Decimal, Field(gt=0)]
ExecutionSide = Literal["buy", "sell"]
ExecutionStatus = Literal["filled", "rejected"]


class MarketOrderRequest(BaseModel):
    symbol: str
    side: ExecutionSide
    quantity: PositiveDecimal

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Symbol must not be empty")
        return normalized


class SimulatedOrderRead(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: Decimal
    requested_price_snapshot: Decimal | None = None
    status: str
    rejection_reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SimulatedFillRead(BaseModel):
    id: int
    order_id: int
    symbol: str
    side: str
    quantity: Decimal
    fill_price: Decimal
    fee: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecutionPositionSnapshot(BaseModel):
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal


class MarketOrderResponse(BaseModel):
    accepted: bool
    status: ExecutionStatus
    message: str
    order: SimulatedOrderRead
    fill: SimulatedFillRead | None = None
    updated_cash_balance: Decimal
    position: ExecutionPositionSnapshot | None = None
