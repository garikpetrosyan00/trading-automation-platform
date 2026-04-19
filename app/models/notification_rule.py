from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

NotificationRuleChannel = Literal["telegram", "email", "webhook", "log"]


class NotificationRule(Base):
    """Configuration rule describing how an alert should be delivered."""

    __tablename__ = "notification_rules"
    __table_args__ = (
        UniqueConstraint(
            "alert_rule_id",
            "channel",
            "target",
            name="uq_notification_rules_alert_rule_id_channel_target",
        ),
        CheckConstraint(
            "channel IN ('telegram', 'email', 'webhook', 'log')",
            name="ck_notification_rules_channel",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    alert_rule_id: Mapped[int] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    message_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    send_on_resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    throttle_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
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

    alert_rule: Mapped["AlertRule"] = relationship(back_populates="notification_rules")
