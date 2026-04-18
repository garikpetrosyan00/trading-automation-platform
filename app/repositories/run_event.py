from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.run_event import RunEvent


class RunEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, run_event: RunEvent) -> RunEvent:
        self.db.add(run_event)
        self.db.commit()
        self.db.refresh(run_event)
        return run_event

    def list_for_run(self, bot_run_id: int, event_type: str | None = None, level: str | None = None) -> list[RunEvent]:
        statement = select(RunEvent).where(RunEvent.bot_run_id == bot_run_id)

        if event_type is not None:
            statement = statement.where(RunEvent.event_type == event_type)
        if level is not None:
            statement = statement.where(RunEvent.level == level)

        statement = statement.order_by(RunEvent.created_at.asc(), RunEvent.id.asc())
        return list(self.db.scalars(statement).all())

    def get_by_id_for_run(self, bot_run_id: int, event_id: int) -> RunEvent | None:
        statement = select(RunEvent).where(RunEvent.bot_run_id == bot_run_id, RunEvent.id == event_id)
        return self.db.scalar(statement)
