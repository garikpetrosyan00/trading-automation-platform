from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

BotStatus = Literal["draft", "active", "paused"]


class Bot(Base):
    """Stored automation instance placeholder linked to a strategy."""

    __tablename__ = "bots"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'paused')", name="ck_bots_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    exchange_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft", index=True)
    is_paper: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    strategy: Mapped["Strategy"] = relationship(back_populates="bots")
    execution_profile: Mapped["ExecutionProfile | None"] = relationship(
        back_populates="bot",
        uselist=False,
    )
    runs: Mapped[list["BotRun"]] = relationship(back_populates="bot")
