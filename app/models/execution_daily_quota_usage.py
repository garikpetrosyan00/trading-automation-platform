from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExecutionDailyQuotaUsage(Base):
    __tablename__ = "execution_daily_quota_usage"
    __table_args__ = (
        UniqueConstraint("bot_id", "utc_day", name="uq_execution_daily_quota_usage_bot_day"),
        CheckConstraint("accepted_order_count >= 0", name="ck_execution_daily_quota_usage_count_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int | None] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), nullable=True, index=True)
    utc_day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    accepted_order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
