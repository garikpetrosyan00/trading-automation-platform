from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaperPositionRead(BaseModel):
    bot_id: int
    symbol: str
    base_asset: str
    quote_asset: str
    quantity: str
    average_entry_price: str
    realized_pnl: str
    market_price: str | None
    unrealized_pnl: str | None
    position_value: str | None
    updated_at: datetime | None


def decimal_to_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")
