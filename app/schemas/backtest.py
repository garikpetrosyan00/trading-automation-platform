from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveDecimal = Annotated[Decimal, Field(gt=0)]


class BacktestRunRequest(BaseModel):
    strategy_id: int
    initial_balance: PositiveDecimal
    source: NonEmptyStr | None = None


class BacktestTradeResponse(BaseModel):
    side: str
    symbol: str
    quantity: Decimal
    price: Decimal
    opened_at: datetime
    cash_balance: Decimal
    realized_pnl: Decimal
    decision_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BacktestResultResponse(BaseModel):
    strategy_id: int
    symbol: str
    timeframe: str
    strategy_type: str
    source: str | None = None
    initial_balance: Decimal
    cash_balance: Decimal
    position_quantity: Decimal
    entry_price: Decimal | None
    final_balance: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    number_of_trades: int
    closed_trades: int
    open_position: bool
    winning_trades: int
    losing_trades: int
    candles_processed: int
    trades: list[BacktestTradeResponse]

    model_config = ConfigDict(from_attributes=True)
