from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.bot_activity import BotActivityItemRead


class BotSummaryRead(BaseModel):
    bot_id: int
    name: str
    status: str
    is_paused: bool
    strategy_type: str | None = None
    symbol: str
    cooldown_seconds: int | None = None
    cooldown_active: bool
    cooldown_until: datetime | None = None
    current_position_qty: Decimal
    last_price: Decimal | None = None
    updated_at: datetime
    buy_below_price: Decimal | None = None
    sell_above_price: Decimal | None = None
    recent_activity: list[BotActivityItemRead]
