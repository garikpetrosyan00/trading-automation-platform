from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BotStatusRead(BaseModel):
    bot_id: int
    bot_name: str
    bot_status: str
    execution_profile_enabled: bool
    runner_enabled: bool
    strategy_type: str | None = None
    symbol: str
    active_run_id: int | None = None
    active_run_status: str | None = None
    latest_price: Decimal | None = None
    current_position_quantity: Decimal | None = None
    cooldown_seconds: int
    cooldown_active: bool
    cooldown_until: datetime | None = None
    last_event_message: str | None = None
    last_event_at: datetime | None = None
    poll_interval_seconds: float
