from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_strategy_id_created_at", "strategy_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(50), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    final_balance: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    number_of_trades: Mapped[int] = mapped_column(nullable=False)
    closed_trades: Mapped[int] = mapped_column(nullable=False)
    open_position: Mapped[bool] = mapped_column(Boolean, nullable=False)
    position_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    winning_trades: Mapped[int] = mapped_column(nullable=False)
    losing_trades: Mapped[int] = mapped_column(nullable=False)
    candles_processed: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
