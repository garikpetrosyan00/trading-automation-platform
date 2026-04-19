from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

AlertRuleOperator = Literal["gt", "gte", "lt", "lte", "eq", "neq", "contains"]
AlertRuleSeverity = Literal["info", "warning", "critical"]


class AlertRule(Base):
    """Configuration rule describing when a bot-related alert should trigger."""

    __tablename__ = "alert_rules"
    __table_args__ = (
        UniqueConstraint("bot_id", "name", name="uq_alert_rules_bot_id_name"),
        CheckConstraint(
            "operator IN ('gt', 'gte', 'lt', 'lte', 'eq', 'neq', 'contains')",
            name="ck_alert_rules_operator",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="ck_alert_rules_severity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(20), nullable=False)
    threshold_value: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="warning",
        server_default="warning",
    )
    cooldown_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    bot: Mapped["Bot"] = relationship(back_populates="alert_rules")
    alert_events: Mapped[list["AlertEvent"]] = relationship(back_populates="alert_rule")
    notification_rules: Mapped[list["NotificationRule"]] = relationship(
        back_populates="alert_rule",
        cascade="all, delete-orphan",
    )
