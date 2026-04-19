from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert_event import AlertEvent


class AlertEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, alert_event: AlertEvent) -> AlertEvent:
        self.db.add(alert_event)
        self.db.commit()
        self.db.refresh(alert_event)
        return alert_event

    def list_for_bot(self, bot_id: int, limit: int | None = None, offset: int | None = None) -> list[AlertEvent]:
        statement = select(AlertEvent).where(AlertEvent.bot_id == bot_id)
        statement = statement.order_by(AlertEvent.triggered_at.desc(), AlertEvent.id.desc())

        if offset is not None:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        return list(self.db.scalars(statement).all())

    def list_for_rule(self, alert_rule_id: int) -> list[AlertEvent]:
        statement = select(AlertEvent).where(AlertEvent.alert_rule_id == alert_rule_id)
        statement = statement.order_by(AlertEvent.triggered_at.desc(), AlertEvent.id.desc())
        return list(self.db.scalars(statement).all())

    def get_by_id(self, alert_event_id: int) -> AlertEvent | None:
        statement = select(AlertEvent).where(AlertEvent.id == alert_event_id)
        return self.db.scalar(statement)

    def get_latest_triggered_for_rule(self, alert_rule_id: int) -> AlertEvent | None:
        statement = select(AlertEvent).where(
            AlertEvent.alert_rule_id == alert_rule_id,
            AlertEvent.status == "triggered",
        )
        statement = statement.order_by(AlertEvent.triggered_at.desc(), AlertEvent.id.desc())
        statement = statement.limit(1)
        return self.db.scalar(statement)
