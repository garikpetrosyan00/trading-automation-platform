from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.execution_daily_quota_usage import ExecutionDailyQuotaUsage


class ExecutionDailyQuotaUsageRepository:
    def __init__(self, db: Session):
        self.db = db

    def ensure_for_day(self, *, bot_id: int | None, utc_day: date) -> None:
        insert_factory = (
            postgresql_insert
            if self.db.bind is not None and self.db.bind.dialect.name == "postgresql"
            else sqlite_insert
        )
        statement = (
            insert_factory(ExecutionDailyQuotaUsage)
            .values(bot_id=bot_id, utc_day=utc_day, accepted_order_count=0)
            .on_conflict_do_nothing(
                index_elements=[
                    ExecutionDailyQuotaUsage.bot_id,
                    ExecutionDailyQuotaUsage.utc_day,
                ]
            )
        )
        self.db.execute(statement)
        self.db.flush()

    def get_for_day(self, *, bot_id: int | None, utc_day: date) -> ExecutionDailyQuotaUsage | None:
        statement = select(ExecutionDailyQuotaUsage).where(ExecutionDailyQuotaUsage.utc_day == utc_day)
        if bot_id is None:
            statement = statement.where(ExecutionDailyQuotaUsage.bot_id.is_(None))
        else:
            statement = statement.where(ExecutionDailyQuotaUsage.bot_id == bot_id)
        return self.db.scalar(statement)

    def get_for_day_for_update(self, *, bot_id: int | None, utc_day: date) -> ExecutionDailyQuotaUsage | None:
        statement = select(ExecutionDailyQuotaUsage).where(ExecutionDailyQuotaUsage.utc_day == utc_day)
        if bot_id is None:
            statement = statement.where(ExecutionDailyQuotaUsage.bot_id.is_(None))
        else:
            statement = statement.where(ExecutionDailyQuotaUsage.bot_id == bot_id)
        return self.db.scalar(statement.with_for_update())

    def increment(self, usage: ExecutionDailyQuotaUsage) -> ExecutionDailyQuotaUsage:
        usage.accepted_order_count += 1
        self.db.add(usage)
        self.db.flush()
        return usage
