from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BotActivityItemRead(BaseModel):
    type: str
    timestamp: datetime
    message: str
    side: str | None = None
    price: Decimal | None = None
    quantity: Decimal | None = None
    cooldown_until: datetime | None = None


class BotActivityRead(BaseModel):
    bot_id: int
    items: list[BotActivityItemRead]


def build_activity_item(run_event, portfolio_repository) -> BotActivityItemRead:
    payload = run_event.payload or {}
    side = payload.get("side")
    price = None
    quantity = None

    fill_id = payload.get("fill_id")
    if fill_id is not None:
        fill = portfolio_repository.get_fill_by_id(fill_id)
        if fill is not None:
            side = fill.side
            price = fill.fill_price
            quantity = fill.quantity

    message = run_event.message
    item_type = "run_event"
    if run_event.message == "order_filled":
        item_type = "order_filled"
        if side in {"buy", "sell"}:
            message = f"{side}_filled"

    return BotActivityItemRead(
        type=item_type,
        timestamp=run_event.created_at,
        message=message,
        side=side,
        price=price,
        quantity=quantity,
        cooldown_until=payload.get("cooldown_until") if run_event.message == "cooldown_active" else None,
    )
