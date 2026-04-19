from sqlalchemy.exc import IntegrityError

from app.core.errors import ConflictError, NotFoundError
from app.models.notification_rule import NotificationRule
from app.repositories.alert_rule import AlertRuleRepository
from app.repositories.notification_rule import NotificationRuleRepository
from app.schemas.notification_rule import NotificationRuleCreate, NotificationRuleUpdate


class NotificationRuleService:
    def __init__(self, repository: NotificationRuleRepository, alert_rule_repository: AlertRuleRepository):
        self.repository = repository
        self.alert_rule_repository = alert_rule_repository

    def create_notification_rule(self, alert_rule_id: int, payload: NotificationRuleCreate) -> NotificationRule:
        self._ensure_alert_rule_exists(alert_rule_id)
        notification_rule = NotificationRule(alert_rule_id=alert_rule_id, **payload.model_dump())
        try:
            return self.repository.create(notification_rule)
        except IntegrityError as exc:
            self.repository.db.rollback()
            raise ConflictError(
                f"Notification rule for channel {payload.channel} and target {payload.target} already exists for alert rule with id {alert_rule_id}",
                error_code="notification_rule_exists",
            ) from exc

    def list_notification_rules(self, alert_rule_id: int) -> list[NotificationRule]:
        self._ensure_alert_rule_exists(alert_rule_id)
        return self.repository.list_for_alert_rule(alert_rule_id)

    def get_notification_rule(self, notification_rule_id: int) -> NotificationRule:
        notification_rule = self.repository.get_by_id(notification_rule_id)
        if notification_rule is None:
            raise NotFoundError(
                f"Notification rule with id {notification_rule_id} was not found",
                error_code="notification_rule_not_found",
            )
        return notification_rule

    def update_notification_rule(self, notification_rule_id: int, payload: NotificationRuleUpdate) -> NotificationRule:
        notification_rule = self.get_notification_rule(notification_rule_id)
        updates = payload.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(notification_rule, field, value)

        try:
            return self.repository.update(notification_rule)
        except IntegrityError as exc:
            self.repository.db.rollback()
            raise ConflictError(
                f"Notification rule for channel {notification_rule.channel} and target {notification_rule.target} already exists for alert rule with id {notification_rule.alert_rule_id}",
                error_code="notification_rule_exists",
            ) from exc

    def delete_notification_rule(self, notification_rule_id: int) -> None:
        notification_rule = self.get_notification_rule(notification_rule_id)
        self.repository.delete(notification_rule)

    def _ensure_alert_rule_exists(self, alert_rule_id: int) -> None:
        if self.alert_rule_repository.get_by_id(alert_rule_id) is None:
            raise NotFoundError(
                f"Alert rule with id {alert_rule_id} was not found",
                error_code="alert_rule_not_found",
            )
