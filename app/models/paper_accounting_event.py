from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaperAccountingEvent(Base):
    __tablename__ = "paper_accounting_events"
    __table_args__ = (
        CheckConstraint("event_type IN ('fill_applied')", name="ck_paper_accounting_events_event_type"),
        CheckConstraint("side IN ('buy', 'sell')", name="ck_paper_accounting_events_side"),
        CheckConstraint("mode = 'paper'", name="ck_paper_accounting_events_mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulated_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fill_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulated_fills.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bot_id: Mapped[int | None] = mapped_column(ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True)
    strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="paper", server_default="paper", index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    realized_pnl_delta: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("0"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
