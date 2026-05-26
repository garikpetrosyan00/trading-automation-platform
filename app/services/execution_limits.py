from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone

from app.repositories.execution_attempt import ExecutionAttemptRepository


ORDER_COUNT_STATUSES = {"filled", "order_created"}


@dataclass(frozen=True)
class DailyOrderCountSnapshot:
    count: int
    day_start: datetime


class ExecutionDailyLimitService:
    def __init__(self, repository: ExecutionAttemptRepository, now_provider=None):
        self.repository = repository
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def count_successful_orders_today(self, *, bot_id: int | None = None) -> DailyOrderCountSnapshot:
        day_start = self._utc_day_start(self.now_provider())
        return DailyOrderCountSnapshot(
            count=self.repository.count_since(
                started_at=day_start,
                bot_id=bot_id,
                final_statuses=ORDER_COUNT_STATUSES,
            ),
            day_start=day_start,
        )

    @staticmethod
    def _utc_day_start(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return datetime.combine(value.date(), time.min, tzinfo=timezone.utc)
