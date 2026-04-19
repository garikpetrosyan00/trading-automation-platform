from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.strategy import NonEmptyStr

NotificationRuleChannel = Literal["telegram", "email", "webhook", "log"]


class NotificationRuleBase(BaseModel):
    channel: NotificationRuleChannel
    target: NonEmptyStr
    message_template: str | None = None
    send_on_resolved: bool = False
    is_enabled: bool = True
    throttle_seconds: int = Field(default=0, ge=0)


class NotificationRuleCreate(NotificationRuleBase):
    pass


class NotificationRuleUpdate(BaseModel):
    channel: NotificationRuleChannel | None = None
    target: NonEmptyStr | None = None
    message_template: str | None = None
    send_on_resolved: bool | None = None
    is_enabled: bool | None = None
    throttle_seconds: int | None = Field(default=None, ge=0)


class NotificationRuleRead(NotificationRuleBase):
    id: int
    alert_rule_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
