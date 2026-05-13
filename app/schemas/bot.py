from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.strategy import PlaceholderSafeStr

BotStatus = Literal["draft", "active", "paused"]


class BotBase(BaseModel):
    name: PlaceholderSafeStr
    exchange_name: PlaceholderSafeStr
    status: BotStatus = "draft"
    is_paper: bool = True
    notes: str | None = None


class BotCreate(BotBase):
    strategy_id: int


class BotUpdate(BaseModel):
    name: PlaceholderSafeStr | None = None
    strategy_id: int | None = None
    exchange_name: PlaceholderSafeStr | None = None
    status: BotStatus | None = None
    is_paper: bool | None = None
    notes: str | None = None


class BotRead(BotBase):
    id: int
    strategy_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
