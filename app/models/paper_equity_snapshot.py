from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaperEquitySnapshot(Base):
    __tablename__ = "paper_equity_snapshots"
    __table_args__ = (
        CheckConstraint("cash_available >= 0", name="ck_paper_equity_snapshots_cash_available_non_negative"),
        CheckConstraint("cash_locked >= 0", name="ck_paper_equity_snapshots_cash_locked_non_negative"),
        CheckConstraint("base_quantity >= 0", name="ck_paper_equity_snapshots_base_quantity_non_negative"),
        CheckConstraint("base_locked >= 0", name="ck_paper_equity_snapshots_base_locked_non_negative"),
        CheckConstraint(
            "event_type IN ('buy_fill', 'sell_fill', 'reset', 'manual_snapshot')",
            name="ck_paper_equity_snapshots_event_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quote_asset: Mapped[str] = mapped_column(String(20), nullable=False)
    cash_available: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    cash_locked: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    base_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    base_locked: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    average_entry_price: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    position_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    total_equity: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulated_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_fill_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulated_fills.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    bot: Mapped["Bot"] = relationship(back_populates="paper_equity_snapshots")
