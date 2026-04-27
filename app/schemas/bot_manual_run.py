from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.bot_activity import BotActivityItemRead

ManualBotRunAction = Literal["bought", "sold", "skipped", "no_action"]


class BotDecisionExplanationRead(BaseModel):
    current_price: Decimal | None = None
    buy_below: Decimal | None = None
    sell_above: Decimal | None = None
    position_qty: Decimal | None = None
    short_window: int | None = None
    long_window: int | None = None
    previous_short_ma: Decimal | None = None
    previous_long_ma: Decimal | None = None
    current_short_ma: Decimal | None = None
    current_long_ma: Decimal | None = None
    candles_used: int | None = None
    decision: str
    reason: str


class BotManualRunRead(BaseModel):
    bot_id: int
    status: str
    is_paused: bool
    action: ManualBotRunAction
    message: str
    cooldown_active: bool
    cooldown_until: datetime | None = None
    current_position_qty: Decimal
    last_price: Decimal | None = None
    decision_explanation: BotDecisionExplanationRead | None = None
    recent_activity_preview: list[BotActivityItemRead]
