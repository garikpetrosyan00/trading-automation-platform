from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bot_run import BotRun

NON_TERMINAL_STATUSES = ("requested", "running")


class BotRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, bot_run: BotRun) -> BotRun:
        self.db.add(bot_run)
        self.db.commit()
        self.db.refresh(bot_run)
        return bot_run

    def get_by_id_for_bot(self, bot_id: int, run_id: int) -> BotRun | None:
        statement = select(BotRun).where(BotRun.bot_id == bot_id, BotRun.id == run_id)
        return self.db.scalar(statement)

    def get_by_id(self, run_id: int) -> BotRun | None:
        statement = select(BotRun).where(BotRun.id == run_id)
        return self.db.scalar(statement)

    def list_for_bot(self, bot_id: int, status: str | None = None, trigger_type: str | None = None) -> list[BotRun]:
        statement = select(BotRun).where(BotRun.bot_id == bot_id)

        if status is not None:
            statement = statement.where(BotRun.status == status)
        if trigger_type is not None:
            statement = statement.where(BotRun.trigger_type == trigger_type)

        statement = statement.order_by(BotRun.created_at.desc(), BotRun.id.desc())
        return list(self.db.scalars(statement).all())

    def get_active_for_bot(self, bot_id: int) -> BotRun | None:
        statement = select(BotRun).where(BotRun.bot_id == bot_id, BotRun.status.in_(NON_TERMINAL_STATUSES))
        return self.db.scalar(statement)

    def update(self, bot_run: BotRun) -> BotRun:
        self.db.add(bot_run)
        self.db.commit()
        self.db.refresh(bot_run)
        return bot_run
