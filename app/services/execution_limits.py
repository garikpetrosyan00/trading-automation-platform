from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal

from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_daily_quota_usage import ExecutionDailyQuotaUsageRepository
from app.repositories.paper_accounting import PaperAccountingRepository


ZERO = Decimal("0")


@dataclass(frozen=True)
class DailyOrderCountSnapshot:
    count: int
    day_start: datetime


@dataclass(frozen=True)
class DailyQuotaReservation:
    allowed: bool
    count: int
    max_daily_order_count: int | None
    utc_day: date
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
        quota_usage_repository: ExecutionDailyQuotaUsageRepository | None = None,
        now_provider=None,
    ):
        self.repository = repository
        self.paper_accounting_repository = paper_accounting_repository
        self.quota_usage_repository = quota_usage_repository or ExecutionDailyQuotaUsageRepository(repository.db)
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def count_successful_orders_today(self, *, bot_id: int | None = None) -> DailyOrderCountSnapshot:
        day_start = self._utc_day_start(self.now_provider())
        usage = self.quota_usage_repository.get_for_day(bot_id=bot_id, utc_day=day_start.date())
        return DailyOrderCountSnapshot(
            count=usage.accepted_order_count if usage is not None else 0,
            day_start=day_start,
        )

    def reserve_accepted_order_quota(
        self,
        *,
        bot_id: int | None,
        max_daily_order_count: int | None,
        enforce_limit: bool,
    ) -> DailyQuotaReservation:
        day_start = self._utc_day_start(self.now_provider())
        utc_day = day_start.date()
        self.quota_usage_repository.ensure_for_day(bot_id=bot_id, utc_day=utc_day)
        usage = self.quota_usage_repository.get_for_day_for_update(bot_id=bot_id, utc_day=utc_day)
        if usage is None:
            raise RuntimeError("Daily execution quota usage row could not be initialized")

        if enforce_limit and max_daily_order_count is not None and max_daily_order_count > 0:
            if usage.accepted_order_count >= max_daily_order_count:
                return DailyQuotaReservation(
                    allowed=False,
                    count=usage.accepted_order_count,
                    max_daily_order_count=max_daily_order_count,
                    utc_day=utc_day,
                    day_start=day_start,
                )

        self.quota_usage_repository.increment(usage)
        return DailyQuotaReservation(
            allowed=True,
            count=usage.accepted_order_count,
            max_daily_order_count=max_daily_order_count,
            utc_day=utc_day,
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
