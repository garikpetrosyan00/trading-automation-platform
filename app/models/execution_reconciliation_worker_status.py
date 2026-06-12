from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExecutionReconciliationWorkerStatus(Base):
    __tablename__ = "execution_reconciliation_worker_status"
    __table_args__ = (
        CheckConstraint(
            "state IN ('running', 'stopped')",
            name="ck_execution_reconciliation_worker_status_state",
        ),
        Index("ix_execution_reconciliation_worker_status_worker_name", "worker_name", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_cycle_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_cycle_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_cycle_result_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_processed_reconciliation_job_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
