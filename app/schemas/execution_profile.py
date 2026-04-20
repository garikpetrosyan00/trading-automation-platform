from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExecutionProfileOrderType = Literal["market", "limit"]
ExecutionProfileStrategyType = Literal["price_threshold"]


class ExecutionProfileBase(BaseModel):
    max_position_size_usd: float = Field(gt=0)
    max_daily_loss_usd: float = Field(gt=0)
    max_open_positions: int = Field(gt=0)
    strategy_type: ExecutionProfileStrategyType = "price_threshold"
    entry_below: Decimal | None = Field(default=None, gt=0)
    exit_above: Decimal | None = Field(default=None, gt=0)
    order_quantity: Decimal | None = Field(default=None, gt=0)
    cooldown_seconds: int = Field(default=60, gt=0)
    default_order_type: ExecutionProfileOrderType = "limit"
    is_enabled: bool = True


class ExecutionProfileCreate(ExecutionProfileBase):
    pass


class ExecutionProfileUpdate(BaseModel):
    max_position_size_usd: float | None = Field(default=None, gt=0)
    max_daily_loss_usd: float | None = Field(default=None, gt=0)
    max_open_positions: int | None = Field(default=None, gt=0)
    strategy_type: ExecutionProfileStrategyType | None = None
    entry_below: Decimal | None = Field(default=None, gt=0)
    exit_above: Decimal | None = Field(default=None, gt=0)
    order_quantity: Decimal | None = Field(default=None, gt=0)
    cooldown_seconds: int | None = Field(default=None, gt=0)
    default_order_type: ExecutionProfileOrderType | None = None
    is_enabled: bool | None = None


class ExecutionProfileRead(ExecutionProfileBase):
    id: int
    bot_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
