from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BotDashboardItemRead(BaseModel):
    bot_id: int
    name: str
    status: str
    is_paused: bool
    strategy_type: str | None = None
    symbol: str
    cooldown_active: bool
    cooldown_until: datetime | None = None
    current_position_qty: Decimal
    last_price: Decimal | None = None
    updated_at: datetime


class BotDashboardRead(BaseModel):
    items: list[BotDashboardItemRead]
