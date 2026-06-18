from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("bot_id", "symbol", name="uq_paper_positions_bot_symbol"),
        CheckConstraint("quantity >= 0", name="ck_paper_positions_quantity_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(20), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    average_entry_price: Mapped[Decimal] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=Decimal("0"),
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

    bot: Mapped["Bot"] = relationship(back_populates="paper_positions")
