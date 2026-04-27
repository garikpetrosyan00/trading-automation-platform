from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "open_time",
            "source",
            name="uq_market_candles_symbol_timeframe_open_time_source",
        ),
        CheckConstraint("open_price > 0", name="ck_market_candles_open_price_positive"),
        CheckConstraint("high_price > 0", name="ck_market_candles_high_price_positive"),
        CheckConstraint("low_price > 0", name="ck_market_candles_low_price_positive"),
        CheckConstraint("close_price > 0", name="ck_market_candles_close_price_positive"),
        CheckConstraint("volume >= 0", name="ck_market_candles_volume_non_negative"),
        CheckConstraint("close_time >= open_time", name="ck_market_candles_close_time_after_open_time"),
        Index("ix_market_candles_symbol_timeframe_open_time", "symbol", "timeframe", "open_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual", server_default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
