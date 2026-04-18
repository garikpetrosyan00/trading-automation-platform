from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RunEvent(Base):
    """Append-only event timeline entry for a bot run."""

    __tablename__ = "run_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('lifecycle', 'log', 'system', 'error')",
            name="ck_run_events_event_type",
        ),
        CheckConstraint(
            "level IN ('info', 'warning', 'error')",
            name="ck_run_events_level",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_run_id: Mapped[int] = mapped_column(ForeignKey("bot_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    bot_run: Mapped["BotRun"] = relationship(back_populates="events")
