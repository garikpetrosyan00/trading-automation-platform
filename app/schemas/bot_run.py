from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

BotRunTriggerType = Literal["manual", "scheduled", "system"]
BotRunStatus = Literal["requested", "running", "succeeded", "failed", "cancelled"]


class BotRunCreate(BaseModel):
    trigger_type: BotRunTriggerType


class BotRunUpdate(BaseModel):
    status: BotRunStatus | None = None
    summary: str | None = None
    error_message: str | None = None


class BotRunRead(BaseModel):
    id: int
    bot_id: int
    trigger_type: BotRunTriggerType
    status: BotRunStatus
    summary: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
