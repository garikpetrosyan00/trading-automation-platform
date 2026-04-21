from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.bot_activity import BotActivityItemRead

ManualBotRunAction = Literal["bought", "sold", "skipped", "no_action"]


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
    recent_activity_preview: list[BotActivityItemRead]
