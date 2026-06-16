from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DraftBalance(Base):
    __tablename__ = "draft_balances"
    __table_args__ = (
        UniqueConstraint("bot_id", "asset", name="uq_draft_balances_bot_asset"),
        CheckConstraint("available >= 0", name="ck_draft_balances_available_non_negative"),
        CheckConstraint("locked >= 0", name="ck_draft_balances_locked_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    available: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("0"), server_default="0")
    locked: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("0"), server_default="0")
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

    bot: Mapped["Bot"] = relationship(back_populates="draft_balances")
