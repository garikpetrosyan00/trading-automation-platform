from fastapi import APIRouter, Response, status

from app.api.dependencies import DbSession
from app.repositories.alert_rule import AlertRuleRepository
from app.repositories.bot import BotRepository
from app.schemas.alert_rule import AlertRuleCreate, AlertRuleRead, AlertRuleUpdate
from app.services.alert_rule import AlertRuleService

router = APIRouter()


def get_alert_rule_service(db: DbSession) -> AlertRuleService:
    return AlertRuleService(AlertRuleRepository(db), BotRepository(db))


@router.post("/bots/{bot_id}/alert-rules", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(bot_id: int, payload: AlertRuleCreate, db: DbSession) -> AlertRuleRead:
    service = get_alert_rule_service(db)
    alert_rule = service.create_alert_rule(bot_id, payload)
    return AlertRuleRead.model_validate(alert_rule)


@router.get("/bots/{bot_id}/alert-rules", response_model=list[AlertRuleRead])
async def list_alert_rules(bot_id: int, db: DbSession) -> list[AlertRuleRead]:
    service = get_alert_rule_service(db)
    alert_rules = service.list_alert_rules(bot_id)
    return [AlertRuleRead.model_validate(alert_rule) for alert_rule in alert_rules]


@router.get("/alert-rules/{alert_rule_id}", response_model=AlertRuleRead)
async def get_alert_rule(alert_rule_id: int, db: DbSession) -> AlertRuleRead:
    service = get_alert_rule_service(db)
    alert_rule = service.get_alert_rule(alert_rule_id)
    return AlertRuleRead.model_validate(alert_rule)


@router.patch("/alert-rules/{alert_rule_id}", response_model=AlertRuleRead)
async def update_alert_rule(alert_rule_id: int, payload: AlertRuleUpdate, db: DbSession) -> AlertRuleRead:
    service = get_alert_rule_service(db)
    alert_rule = service.update_alert_rule(alert_rule_id, payload)
    return AlertRuleRead.model_validate(alert_rule)


@router.delete("/alert-rules/{alert_rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(alert_rule_id: int, db: DbSession) -> Response:
    service = get_alert_rule_service(db)
    service.delete_alert_rule(alert_rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
