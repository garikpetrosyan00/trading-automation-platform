from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PositiveDecimal = Annotated[Decimal, Field(gt=0)]
ExecutionSide = Literal["buy", "sell"]
ExecutionStatus = Literal["filled", "rejected"]
ExecutionAuditStatus = Literal["created", "submitted", "filled", "rejected", "cancelled"]
ExecutionAuditMode = Literal["paper", "live"]


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


class ExecutionFillAuditRead(BaseModel):
    id: int
    order_id: int
    symbol: str
    side: ExecutionSide
    fill_price: Decimal
    fill_quantity: Decimal
    fee: Decimal
    source: str
    filled_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecutionOrderAuditRead(BaseModel):
    id: int
    bot_id: int | None = None
    strategy_id: int | None = None
    symbol: str
    side: ExecutionSide
    order_type: str
    mode: ExecutionAuditMode
    quantity: Decimal
    requested_price: Decimal | None = None
    requested_price_snapshot: Decimal | None = None
    status: ExecutionAuditStatus
    decision_reason: str | None = None
    decision_metadata: dict | None = None
    rejection_reason: str | None = None
    fill_count: int
    fills: list[ExecutionFillAuditRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None


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
