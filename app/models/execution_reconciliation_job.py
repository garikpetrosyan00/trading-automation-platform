from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExecutionReconciliationJob(Base):
    __tablename__ = "execution_reconciliation_jobs"
    __table_args__ = (
        UniqueConstraint("execution_attempt_id", name="uq_execution_reconciliation_jobs_attempt"),
        CheckConstraint(
            "state IN ('pending', 'claimed', 'resolved', 'exhausted')",
            name="ck_execution_reconciliation_jobs_state",
        ),
        CheckConstraint(
            "automatic_attempt_count >= 0",
            name="ck_execution_reconciliation_jobs_attempt_count_non_negative",
        ),
        Index("ix_execution_reconciliation_jobs_state_next_attempt_at", "state", "next_attempt_at"),
        Index("ix_execution_reconciliation_jobs_state_lease_expires_at", "state", "lease_expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    execution_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("execution_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending", index=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    automatic_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_resolution: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_failure_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
