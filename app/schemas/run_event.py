from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.strategy import NonEmptyStr

RunEventType = Literal["lifecycle", "log", "system", "error"]
RunEventLevel = Literal["info", "warning", "error"]


class RunEventCreate(BaseModel):
    event_type: RunEventType
    level: RunEventLevel
    message: NonEmptyStr
    payload: dict[str, Any] | None = None


class RunEventRead(BaseModel):
    id: int
    bot_run_id: int
    event_type: RunEventType
    level: RunEventLevel
    message: str
    payload: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
