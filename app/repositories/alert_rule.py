from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert_rule import AlertRule


class AlertRuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, alert_rule: AlertRule) -> AlertRule:
        self.db.add(alert_rule)
        self.db.commit()
        self.db.refresh(alert_rule)
        return alert_rule

    def list_for_bot(self, bot_id: int) -> list[AlertRule]:
        statement = select(AlertRule).where(AlertRule.bot_id == bot_id).order_by(AlertRule.created_at.desc(), AlertRule.id.desc())
        return list(self.db.scalars(statement).all())

    def list_enabled_for_bot(self, bot_id: int) -> list[AlertRule]:
        statement = select(AlertRule).where(
            AlertRule.bot_id == bot_id,
            AlertRule.is_enabled.is_(True),
        )
        statement = statement.order_by(AlertRule.created_at.desc(), AlertRule.id.desc())
        return list(self.db.scalars(statement).all())

    def get_by_id(self, alert_rule_id: int) -> AlertRule | None:
        statement = select(AlertRule).where(AlertRule.id == alert_rule_id)
        return self.db.scalar(statement)

    def update(self, alert_rule: AlertRule) -> AlertRule:
        self.db.add(alert_rule)
        self.db.commit()
        self.db.refresh(alert_rule)
        return alert_rule

    def delete(self, alert_rule: AlertRule) -> None:
        self.db.delete(alert_rule)
        self.db.commit()
