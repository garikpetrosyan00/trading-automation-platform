from fastapi import APIRouter, Query, status

from app.api.dependencies import DbSession
from app.repositories.alert_event import AlertEventRepository
from app.repositories.alert_rule import AlertRuleRepository
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.run_event import RunEventRepository
from app.schemas.alert_event import AlertEvaluationRequest, AlertEvaluationResponse, AlertEventRead
from app.services.alert_event import AlertEventService

router = APIRouter()


def get_alert_event_service(db: DbSession) -> AlertEventService:
    return AlertEventService(
        AlertEventRepository(db),
        BotRepository(db),
        BotRunRepository(db),
        AlertRuleRepository(db),
        RunEventRepository(db),
    )


@router.post("/bots/{bot_id}/alerts/evaluate", response_model=AlertEvaluationResponse, status_code=status.HTTP_200_OK)
async def evaluate_alerts(bot_id: int, payload: AlertEvaluationRequest, db: DbSession) -> AlertEvaluationResponse:
    service = get_alert_event_service(db)
    result = service.evaluate_alerts_for_bot(bot_id, bot_run_id=payload.bot_run_id, force=payload.force)
    triggered_events = [AlertEventRead.model_validate(alert_event) for alert_event in result["triggered_events"]]
    return AlertEvaluationResponse(
        bot_id=result["bot_id"],
        bot_run_id=result["bot_run_id"],
        evaluated_rules_count=result["evaluated_rules_count"],
        triggered_events_count=len(triggered_events),
        triggered_events=triggered_events,
    )


@router.get("/bots/{bot_id}/alert-events", response_model=list[AlertEventRead])
async def list_alert_events_for_bot(
    bot_id: int,
    db: DbSession,
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
) -> list[AlertEventRead]:
    service = get_alert_event_service(db)
    alert_events = service.list_alert_events_for_bot(bot_id, limit=limit, offset=offset)
    return [AlertEventRead.model_validate(alert_event) for alert_event in alert_events]


@router.get("/alert-rules/{alert_rule_id}/alert-events", response_model=list[AlertEventRead])
async def list_alert_events_for_rule(alert_rule_id: int, db: DbSession) -> list[AlertEventRead]:
    service = get_alert_event_service(db)
    alert_events = service.list_alert_events_for_rule(alert_rule_id)
    return [AlertEventRead.model_validate(alert_event) for alert_event in alert_events]


@router.get("/alert-events/{alert_event_id}", response_model=AlertEventRead)
async def get_alert_event(alert_event_id: int, db: DbSession) -> AlertEventRead:
    service = get_alert_event_service(db)
    alert_event = service.get_alert_event(alert_event_id)
    return AlertEventRead.model_validate(alert_event)
