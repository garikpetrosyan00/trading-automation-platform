from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExecutionProfile(Base):
    """Stored runtime and risk configuration placeholder for a bot."""

    __tablename__ = "execution_profiles"
    __table_args__ = (
        CheckConstraint(
            "default_order_type IN ('market', 'limit')",
            name="ck_execution_profiles_default_order_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    max_position_size_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_daily_loss_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_open_positions: Mapped[int] = mapped_column(nullable=False)
    default_order_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="limit",
        server_default="limit",
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
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

    bot: Mapped["Bot"] = relationship(back_populates="execution_profile")
