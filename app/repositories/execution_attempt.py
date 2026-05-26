from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution_attempt import ExecutionAttempt


class ExecutionAttemptRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        self.db.add(attempt)
        self.db.flush()
        return attempt

    def update(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        self.db.add(attempt)
        self.db.flush()
        return attempt

    def get_by_id(self, attempt_id: int) -> ExecutionAttempt | None:
        statement = select(ExecutionAttempt).where(ExecutionAttempt.id == attempt_id)
        return self.db.scalar(statement)

    def list_filtered(
        self,
        *,
        bot_id: int | None = None,
        strategy_id: int | None = None,
        symbol: str | None = None,
        side: str | None = None,
        mode: str | None = None,
        final_status: str | None = None,
        reason: str | None = None,
        limit: int = 50,
    ) -> list[ExecutionAttempt]:
        statement = select(ExecutionAttempt)
        if bot_id is not None:
            statement = statement.where(ExecutionAttempt.bot_id == bot_id)
        if strategy_id is not None:
            statement = statement.where(ExecutionAttempt.strategy_id == strategy_id)
        if symbol is not None:
            statement = statement.where(ExecutionAttempt.symbol == symbol.upper())
        if side is not None:
            statement = statement.where(ExecutionAttempt.side == side)
        if mode is not None:
            statement = statement.where(ExecutionAttempt.mode == mode)
        if final_status is not None:
            statement = statement.where(ExecutionAttempt.final_status == final_status)
        if reason is not None:
            statement = statement.where(ExecutionAttempt.final_reason == reason)
        statement = statement.order_by(ExecutionAttempt.created_at.desc(), ExecutionAttempt.id.desc()).limit(limit)
        return list(self.db.scalars(statement).all())
