from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification_rule import NotificationRule


class NotificationRuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, notification_rule: NotificationRule) -> NotificationRule:
        self.db.add(notification_rule)
        self.db.commit()
        self.db.refresh(notification_rule)
        return notification_rule

    def list_for_alert_rule(self, alert_rule_id: int) -> list[NotificationRule]:
        statement = select(NotificationRule).where(NotificationRule.alert_rule_id == alert_rule_id)
        statement = statement.order_by(NotificationRule.created_at.desc(), NotificationRule.id.desc())
        return list(self.db.scalars(statement).all())

    def get_by_id(self, notification_rule_id: int) -> NotificationRule | None:
        statement = select(NotificationRule).where(NotificationRule.id == notification_rule_id)
        return self.db.scalar(statement)

    def update(self, notification_rule: NotificationRule) -> NotificationRule:
        self.db.add(notification_rule)
        self.db.commit()
        self.db.refresh(notification_rule)
        return notification_rule

    def delete(self, notification_rule: NotificationRule) -> None:
        self.db.delete(notification_rule)
        self.db.commit()
