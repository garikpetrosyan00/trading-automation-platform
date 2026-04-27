from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_candle import MarketCandle


class MarketCandleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_unique_key(
        self,
        *,
        symbol: str,
        timeframe: str,
        open_time: datetime,
        source: str,
    ) -> MarketCandle | None:
        statement = select(MarketCandle).where(
            MarketCandle.symbol == symbol,
            MarketCandle.timeframe == timeframe,
            MarketCandle.open_time == open_time,
            MarketCandle.source == source,
        )
        return self.db.scalar(statement)

    def upsert(self, candle: MarketCandle) -> MarketCandle:
        existing = self.get_by_unique_key(
            symbol=candle.symbol,
            timeframe=candle.timeframe,
            open_time=candle.open_time,
            source=candle.source,
        )

        if existing is None:
            self.db.add(candle)
            self.db.commit()
            self.db.refresh(candle)
            return candle

        existing.close_time = candle.close_time
        existing.open_price = candle.open_price
        existing.high_price = candle.high_price
        existing.low_price = candle.low_price
        existing.close_price = candle.close_price
        existing.volume = candle.volume
        self.db.add(existing)
        self.db.commit()
        self.db.refresh(existing)
        return existing

    def list_recent(self, *, symbol: str, timeframe: str, limit: int) -> list[MarketCandle]:
        recent_statement = (
            select(MarketCandle)
            .where(MarketCandle.symbol == symbol, MarketCandle.timeframe == timeframe)
            .order_by(MarketCandle.open_time.desc(), MarketCandle.id.desc())
            .limit(limit)
        )
        recent = list(self.db.scalars(recent_statement).all())
        return sorted(recent, key=lambda candle: (candle.open_time, candle.id))
