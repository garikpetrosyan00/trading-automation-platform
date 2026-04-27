from app.models.market_candle import MarketCandle
from app.repositories.market_candle import MarketCandleRepository
from app.schemas.market import MarketCandleCreate


class MarketCandleService:
    def __init__(self, repository: MarketCandleRepository):
        self.repository = repository

    def upsert(self, payload: MarketCandleCreate) -> MarketCandle:
        candle = MarketCandle(**payload.model_dump())
        return self.repository.upsert(candle)

    def upsert_many(self, payloads: list[MarketCandleCreate]) -> list[MarketCandle]:
        return [self.upsert(payload) for payload in payloads]

    def list_recent(self, *, symbol: str, timeframe: str, limit: int) -> list[MarketCandle]:
        return self.repository.list_recent(symbol=symbol, timeframe=timeframe, limit=limit)
