from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BotPerformanceRead(BaseModel):
    bot_id: int
    name: str
    symbol: str
    strategy_type: str | None = None
    latest_market_price: Decimal | None = None
    current_position_quantity: Decimal | None = None
    last_decision: str | None = None
    last_decision_reason: str | None = None
    last_run_event_at: datetime | None = None
    recent_run_event_count: int
    buy_decision_count: int
    sell_decision_count: int
    hold_decision_count: int
    risk_blocked_event_count: int
    filled_order_event_count: int
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    health: str
