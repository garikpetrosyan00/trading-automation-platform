from fastapi import APIRouter, Response, status

from app.api.dependencies import DbSession
from app.repositories.alert_rule import AlertRuleRepository
from app.repositories.notification_rule import NotificationRuleRepository
from app.schemas.notification_rule import NotificationRuleCreate, NotificationRuleRead, NotificationRuleUpdate
from app.services.notification_rule import NotificationRuleService

router = APIRouter()


def get_notification_rule_service(db: DbSession) -> NotificationRuleService:
    return NotificationRuleService(NotificationRuleRepository(db), AlertRuleRepository(db))


@router.post(
    "/alert-rules/{alert_rule_id}/notification-rules",
    response_model=NotificationRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_rule(
    alert_rule_id: int,
    payload: NotificationRuleCreate,
    db: DbSession,
) -> NotificationRuleRead:
    service = get_notification_rule_service(db)
    notification_rule = service.create_notification_rule(alert_rule_id, payload)
    return NotificationRuleRead.model_validate(notification_rule)


@router.get("/alert-rules/{alert_rule_id}/notification-rules", response_model=list[NotificationRuleRead])
async def list_notification_rules(alert_rule_id: int, db: DbSession) -> list[NotificationRuleRead]:
    service = get_notification_rule_service(db)
    notification_rules = service.list_notification_rules(alert_rule_id)
    return [NotificationRuleRead.model_validate(notification_rule) for notification_rule in notification_rules]


@router.get("/notification-rules/{notification_rule_id}", response_model=NotificationRuleRead)
async def get_notification_rule(notification_rule_id: int, db: DbSession) -> NotificationRuleRead:
    service = get_notification_rule_service(db)
    notification_rule = service.get_notification_rule(notification_rule_id)
    return NotificationRuleRead.model_validate(notification_rule)


@router.patch("/notification-rules/{notification_rule_id}", response_model=NotificationRuleRead)
async def update_notification_rule(
    notification_rule_id: int,
    payload: NotificationRuleUpdate,
    db: DbSession,
) -> NotificationRuleRead:
    service = get_notification_rule_service(db)
    notification_rule = service.update_notification_rule(notification_rule_id, payload)
    return NotificationRuleRead.model_validate(notification_rule)


@router.delete("/notification-rules/{notification_rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_rule(notification_rule_id: int, db: DbSession) -> Response:
    service = get_notification_rule_service(db)
    service.delete_notification_rule(notification_rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
