from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.paper_accounting_event import PaperAccountingEvent


class PaperAccountingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, event: PaperAccountingEvent) -> PaperAccountingEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def sum_realized_pnl_since(self, *, started_at: datetime, ended_before: datetime | None = None) -> Decimal:
        statement = select(func.coalesce(func.sum(PaperAccountingEvent.realized_pnl_delta), Decimal("0"))).where(
            PaperAccountingEvent.mode == "paper",
            PaperAccountingEvent.occurred_at >= started_at,
        )
        if ended_before is not None:
            statement = statement.where(PaperAccountingEvent.occurred_at < ended_before)
        return self.db.scalar(statement) or Decimal("0")

    def list_events(self) -> list[PaperAccountingEvent]:
        statement = select(PaperAccountingEvent).order_by(
            PaperAccountingEvent.occurred_at.desc(),
            PaperAccountingEvent.id.desc(),
        )
        return list(self.db.scalars(statement).all())
