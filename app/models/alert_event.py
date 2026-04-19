from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AlertEvent(Base):
    """Historical record of an alert rule match."""

    __tablename__ = "alert_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('triggered', 'resolved', 'suppressed')",
            name="ck_alert_events_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    bot_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("bot_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    alert_rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="triggered",
        server_default="triggered",
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(20), nullable=False)
    threshold_value: Mapped[str] = mapped_column(String(255), nullable=False)
    actual_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    bot: Mapped["Bot"] = relationship(back_populates="alert_events")
    bot_run: Mapped["BotRun | None"] = relationship(back_populates="alert_events")
    alert_rule: Mapped["AlertRule"] = relationship(back_populates="alert_events")
