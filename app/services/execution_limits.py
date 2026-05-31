from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from decimal import Decimal

from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_accounting import PaperAccountingRepository


ORDER_COUNT_STATUSES = {"created", "filled", "order_created"}
ZERO = Decimal("0")


@dataclass(frozen=True)
class DailyOrderCountSnapshot:
    count: int
    day_start: datetime


@dataclass(frozen=True)
class DailyLossSnapshot:
    realized_pnl: Decimal
    realized_loss: Decimal
    day_start: datetime


class ExecutionDailyLimitService:
    def __init__(
        self,
        repository: ExecutionAttemptRepository,
        paper_accounting_repository: PaperAccountingRepository | None = None,
        now_provider=None,
    ):
        self.repository = repository
        self.paper_accounting_repository = paper_accounting_repository
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

    def get_realized_loss_today(self) -> DailyLossSnapshot:
        day_start = self._utc_day_start(self.now_provider())
        if self.paper_accounting_repository is None:
            return DailyLossSnapshot(realized_pnl=ZERO, realized_loss=ZERO, day_start=day_start)

        realized_pnl = self.paper_accounting_repository.sum_realized_pnl_since(started_at=day_start)
        realized_loss = -realized_pnl if realized_pnl < ZERO else ZERO
        return DailyLossSnapshot(
            realized_pnl=realized_pnl,
            realized_loss=realized_loss,
            day_start=day_start,
        )

    @staticmethod
    def _utc_day_start(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return datetime.combine(value.date(), time.min, tzinfo=timezone.utc)
