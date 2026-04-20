from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
