from datetime import datetime
from decimal import Decimal

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

PositiveDecimal = Annotated[Decimal, Field(gt=0)]


class PortfolioSummaryRead(BaseModel):
    base_currency: str
    starting_cash: Decimal
    cash_balance: Decimal
    market_value: Decimal
    equity: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal


class PositionRead(BaseModel):
    id: int
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal
    latest_price: Decimal | None = None
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaperPortfolioPositionRead(BaseModel):
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal
    latest_price: Decimal | None = None
    latest_market_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_percent: Decimal | None = None
    realized_pnl: Decimal
    price_available: bool = False
    updated_at: datetime


class PaperPortfolioSnapshotRead(BaseModel):
    base_currency: str
    account_currency: str
    starting_balance: Decimal
    cash_balance: Decimal
    total_realized_pnl: Decimal
    positions: list[PaperPortfolioPositionRead]
    positions_market_value: Decimal
    total_market_value: Decimal | None = None
    total_unrealized_pnl: Decimal | None = None
    total_equity: Decimal | None = None
    open_position_count: int
    updated_at: datetime | None = None


class PaperPortfolioResetRequest(BaseModel):
    starting_balance: PositiveDecimal


class PaperPortfolioResetRead(BaseModel):
    base_currency: str
    starting_balance: Decimal
    cash_balance: Decimal
    total_realized_pnl: Decimal
    reset_at: datetime
