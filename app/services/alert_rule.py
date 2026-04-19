from sqlalchemy.exc import IntegrityError

from app.core.errors import ConflictError, NotFoundError
from app.models.alert_rule import AlertRule
from app.repositories.alert_rule import AlertRuleRepository
from app.repositories.bot import BotRepository
from app.schemas.alert_rule import AlertRuleCreate, AlertRuleUpdate


class AlertRuleService:
    def __init__(self, repository: AlertRuleRepository, bot_repository: BotRepository):
        self.repository = repository
        self.bot_repository = bot_repository

    def create_alert_rule(self, bot_id: int, payload: AlertRuleCreate) -> AlertRule:
        self._ensure_bot_exists(bot_id)
        alert_rule = AlertRule(bot_id=bot_id, **payload.model_dump())
        try:
            return self.repository.create(alert_rule)
        except IntegrityError as exc:
            self.repository.db.rollback()
            raise ConflictError(
                f"Alert rule with name {payload.name} already exists for bot with id {bot_id}",
                error_code="alert_rule_exists",
            ) from exc

    def list_alert_rules(self, bot_id: int) -> list[AlertRule]:
        self._ensure_bot_exists(bot_id)
        return self.repository.list_for_bot(bot_id)

    def get_alert_rule(self, alert_rule_id: int) -> AlertRule:
        alert_rule = self.repository.get_by_id(alert_rule_id)
        if alert_rule is None:
            raise NotFoundError(
                f"Alert rule with id {alert_rule_id} was not found",
                error_code="alert_rule_not_found",
            )
        return alert_rule

    def update_alert_rule(self, alert_rule_id: int, payload: AlertRuleUpdate) -> AlertRule:
        alert_rule = self.get_alert_rule(alert_rule_id)
        updates = payload.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(alert_rule, field, value)

        try:
            return self.repository.update(alert_rule)
        except IntegrityError as exc:
            self.repository.db.rollback()
            raise ConflictError(
                f"Alert rule with name {alert_rule.name} already exists for bot with id {alert_rule.bot_id}",
                error_code="alert_rule_exists",
            ) from exc

    def delete_alert_rule(self, alert_rule_id: int) -> None:
        alert_rule = self.get_alert_rule(alert_rule_id)
        try:
            self.repository.delete(alert_rule)
        except IntegrityError as exc:
            self.repository.db.rollback()
            raise ConflictError(
                f"Alert rule with id {alert_rule_id} cannot be deleted because alert history exists",
                error_code="alert_rule_has_history",
            ) from exc

    def _ensure_bot_exists(self, bot_id: int) -> None:
        if self.bot_repository.get_by_id(bot_id) is None:
            raise NotFoundError(
                f"Bot with id {bot_id} was not found",
                error_code="bot_not_found",
            )
