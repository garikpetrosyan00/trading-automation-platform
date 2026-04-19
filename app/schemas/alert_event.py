from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.alert_rule import AlertRuleOperator, AlertRuleSeverity


class AlertEventRead(BaseModel):
    id: int
    bot_id: int
    bot_run_id: int | None
    alert_rule_id: int
    status: str
    severity: AlertRuleSeverity
    field_name: str
    operator: AlertRuleOperator
    threshold_value: str
    actual_value: str | None
    title: str
    message: str | None
    triggered_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertEvaluationRequest(BaseModel):
    bot_run_id: int | None = None
    force: bool = False


class AlertEvaluationResponse(BaseModel):
    bot_id: int
    bot_run_id: int | None
    evaluated_rules_count: int
    triggered_events_count: int
    triggered_events: list[AlertEventRead]
