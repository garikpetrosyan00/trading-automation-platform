from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BotRun(Base):
    """Historical run record for a bot lifecycle attempt."""

    __tablename__ = "bot_runs"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('manual', 'scheduled', 'system')",
            name="ck_bot_runs_trigger_type",
        ),
        CheckConstraint(
            "status IN ('requested', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_bot_runs_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="requested",
        server_default="requested",
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    bot: Mapped["Bot"] = relationship(back_populates="runs")
