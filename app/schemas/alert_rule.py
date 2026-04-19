from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.strategy import NonEmptyStr

AlertRuleOperator = Literal["gt", "gte", "lt", "lte", "eq", "neq", "contains"]
AlertRuleSeverity = Literal["info", "warning", "critical"]


class AlertRuleBase(BaseModel):
    name: NonEmptyStr
    description: str | None = None
    field_name: NonEmptyStr
    operator: AlertRuleOperator
    threshold_value: NonEmptyStr
    severity: AlertRuleSeverity = "warning"
    cooldown_seconds: int = Field(default=0, ge=0)
    is_enabled: bool = True


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    name: NonEmptyStr | None = None
    description: str | None = None
    field_name: NonEmptyStr | None = None
    operator: AlertRuleOperator | None = None
    threshold_value: NonEmptyStr | None = None
    severity: AlertRuleSeverity | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0)
    is_enabled: bool | None = None


class AlertRuleRead(AlertRuleBase):
    id: int
    bot_id: int
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
