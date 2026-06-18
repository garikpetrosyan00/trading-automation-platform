from datetime import datetime

from pydantic import BaseModel


class PaperEquitySnapshotItemRead(BaseModel):
    id: int
    bot_id: int
    symbol: str
    quote_asset: str
    cash_available: str
    cash_locked: str
    base_quantity: str
    base_locked: str
    average_entry_price: str
    realized_pnl: str
    market_price: str | None
    position_value: str | None
    total_equity: str | None
    event_type: str
    created_at: datetime


class PaperEquitySnapshotListRead(BaseModel):
    bot_id: int
    count: int
    items: list[PaperEquitySnapshotItemRead]
