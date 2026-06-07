from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PositiveDecimal = Annotated[Decimal, Field(gt=0)]
ExecutionSide = Literal["buy", "sell"]
ExecutionStatus = Literal["filled", "rejected"]
ExecutionAuditStatus = Literal["created", "submitted", "filled", "rejected", "cancelled"]
ExecutionAuditMode = Literal["paper", "live"]
ExecutionAttemptMode = Literal["paper", "testnet", "live"]
ExecutionAttemptStatus = Literal[
    "created",
    "blocked_by_risk",
    "blocked_by_safety",
    "rejected_by_broker",
    "order_created",
    "filled",
    "failed",
]


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


class ExecutionAttemptRead(BaseModel):
    id: int
    bot_id: int | None = None
    strategy_id: int | None = None
    order_id: int | None = None
    symbol: str
    side: ExecutionSide
    mode: ExecutionAttemptMode
    broker: str | None = None
    requested_quantity: Decimal
    requested_price: Decimal | None = None
    decision_reason: str | None = None
    risk_status: str | None = None
    safety_status: str | None = None
    final_status: ExecutionAttemptStatus
    final_reason: str | None = None
    metadata: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecutionReconciliationAttemptRead(BaseModel):
    attempt_id: int
    bot_id: int | None = None
    created_at: datetime
    symbol: str
    side: ExecutionSide
    quantity: Decimal
    reason: str | None = None
    new_client_order_id: str | None = None
    submission_status_unknown: bool = False
    reconciliation_attempted: bool = False
    reconciliation_trigger: str | None = None
    reconciliation_resolution: str | None = None
    submission_recovered: bool = False
    recovered_order_status: str | None = None
    binance_order_id: str | None = None


class ExecutionReconciliationStatusRead(BaseModel):
    bot_id: int
    unresolved_unknown_count: int
    recovered_count: int
    latest_unresolved_at: datetime | None = None
    latest_recovered_at: datetime | None = None
    recent_attempts: list[ExecutionReconciliationAttemptRead] = Field(default_factory=list)


class ExecutionSafetyStatusRead(BaseModel):
    global_execution_enabled: bool
    live_execution_enabled: bool
    paper_execution_allowed: bool
    binance_testnet_broker_enabled: bool
    binance_testnet_order_submission_enabled: bool
    binance_testnet_credentials_configured: bool
    max_order_notional: Decimal | None = None
    max_daily_order_count: int | None = None
    max_daily_loss: Decimal | None = None
    utc_day_start: datetime
    current_daily_attempt_count: int
    remaining_daily_order_capacity: int | None = None
    current_daily_realized_pnl: Decimal = Decimal("0")
    current_daily_realized_loss: Decimal = Decimal("0")
    remaining_daily_loss_capacity: Decimal | None = None
    is_daily_loss_limit_exceeded: bool = False
    is_execution_currently_allowed: bool
    blocking_reason: str | None = None
    metadata: dict = Field(default_factory=dict)


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
