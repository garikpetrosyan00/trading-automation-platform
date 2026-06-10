from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.bot import Bot
from app.models.execution_attempt import ExecutionAttempt

RECONCILIATION_FINAL_REASONS = frozenset(
    {
        "testnet_order_reconciliation_unresolved",
        "testnet_order_recovered_after_unknown_submission",
    }
)


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

    def count_since(
        self,
        *,
        started_at: datetime,
        bot_id: int | None = None,
        strategy_id: int | None = None,
        final_statuses: set[str] | None = None,
    ) -> int:
        statement = select(func.count()).select_from(ExecutionAttempt).where(ExecutionAttempt.created_at >= started_at)
        if bot_id is not None:
            statement = statement.where(ExecutionAttempt.bot_id == bot_id)
        if strategy_id is not None:
            statement = statement.where(ExecutionAttempt.strategy_id == strategy_id)
        if final_statuses is not None:
            statement = statement.where(ExecutionAttempt.final_status.in_(final_statuses))
        return int(self.db.scalar(statement) or 0)

    def list_reconciliation_related_for_bot(self, *, bot_id: int, limit: int) -> list[ExecutionAttempt]:
        statement = (
            select(ExecutionAttempt)
            .where(
                ExecutionAttempt.bot_id == bot_id,
                self._reconciliation_filter(),
            )
            .order_by(ExecutionAttempt.created_at.desc(), ExecutionAttempt.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def count_unresolved_reconciliation_for_bot(self, *, bot_id: int) -> int:
        statement = (
            select(func.count())
            .select_from(ExecutionAttempt)
            .where(
                ExecutionAttempt.bot_id == bot_id,
                self._unresolved_reconciliation_filter(),
            )
        )
        return int(self.db.scalar(statement) or 0)

    def has_unresolved_testnet_submission_for_bot(self, *, bot_id: int) -> bool:
        metadata = ExecutionAttempt.metadata_
        statement = (
            select(ExecutionAttempt.id)
            .where(
                ExecutionAttempt.bot_id == bot_id,
                ExecutionAttempt.mode == "testnet",
                ExecutionAttempt.broker == "binance_testnet",
                or_(
                    ExecutionAttempt.final_reason == "testnet_order_reconciliation_unresolved",
                    and_(
                        metadata["submission_status_unknown"].as_boolean().is_(True),
                        metadata["submission_recovered"].as_boolean().is_not(True),
                        metadata["reconciliation_resolution"].as_string() == "unresolved",
                    ),
                ),
            )
            .limit(1)
        )
        return self.db.scalar(statement) is not None

    def lock_bot_submission_scope(self, *, bot_id: int) -> bool:
        statement = select(Bot.id).where(Bot.id == bot_id).with_for_update()
        return self.db.scalar(statement) is not None

    def count_recovered_reconciliation_for_bot(self, *, bot_id: int) -> int:
        statement = (
            select(func.count())
            .select_from(ExecutionAttempt)
            .where(
                ExecutionAttempt.bot_id == bot_id,
                self._recovered_reconciliation_filter(),
            )
        )
        return int(self.db.scalar(statement) or 0)

    def latest_unresolved_reconciliation_at_for_bot(self, *, bot_id: int) -> datetime | None:
        statement = select(func.max(ExecutionAttempt.created_at)).where(
            ExecutionAttempt.bot_id == bot_id,
            self._unresolved_reconciliation_filter(),
        )
        return self.db.scalar(statement)

    def latest_recovered_reconciliation_at_for_bot(self, *, bot_id: int) -> datetime | None:
        statement = select(func.max(ExecutionAttempt.created_at)).where(
            ExecutionAttempt.bot_id == bot_id,
            self._recovered_reconciliation_filter(),
        )
        return self.db.scalar(statement)

    @staticmethod
    def _reconciliation_filter():
        metadata = ExecutionAttempt.metadata_
        return or_(
            ExecutionAttempt.final_reason.in_(RECONCILIATION_FINAL_REASONS),
            metadata["submission_status_unknown"].as_boolean().is_(True),
            metadata["reconciliation_attempted"].as_boolean().is_(True),
        )

    @staticmethod
    def _unresolved_reconciliation_filter():
        metadata = ExecutionAttempt.metadata_
        return or_(
            ExecutionAttempt.final_reason == "testnet_order_reconciliation_unresolved",
            metadata["reconciliation_resolution"].as_string() == "unresolved",
        )

    @staticmethod
    def _recovered_reconciliation_filter():
        metadata = ExecutionAttempt.metadata_
        return or_(
            ExecutionAttempt.final_reason == "testnet_order_recovered_after_unknown_submission",
            metadata["submission_recovered"].as_boolean().is_(True),
        )
