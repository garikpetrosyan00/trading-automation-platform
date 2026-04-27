from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import DbSession, MarketDataServiceDep
from app.core.config import get_settings
from app.repositories.market_candle import MarketCandleRepository
from app.schemas.market import (
    BinanceMarketCandlesRead,
    BinanceMarketCandlesRequest,
    BinanceMarketPriceRead,
    MarketCandleCreate,
    MarketCandleRead,
    MarketPriceRead,
    MarketPriceUpdateRequest,
    MarketSymbolRequest,
)
from app.services.binance_market_data import BinanceMarketDataClient
from app.services.market_candle import MarketCandleService

router = APIRouter(prefix="/market")


def get_binance_market_data_client() -> BinanceMarketDataClient:
    settings = get_settings()
    return BinanceMarketDataClient(base_url=settings.binance_market_data_base_url)


def get_market_candle_service(db: DbSession) -> MarketCandleService:
    return MarketCandleService(MarketCandleRepository(db))


@router.post("/price", response_model=MarketPriceRead)
async def set_market_price(
    payload: MarketPriceUpdateRequest,
    market_data_service: MarketDataServiceDep,
) -> MarketPriceRead:
    event = market_data_service.set_price(payload.symbol, payload.price)
    return MarketPriceRead(symbol=event.symbol, price=event.price, updated_at=event.received_at)


@router.post("/binance/price", response_model=BinanceMarketPriceRead)
async def fetch_binance_market_price(
    payload: MarketSymbolRequest,
    market_data_service: MarketDataServiceDep,
    binance_client: BinanceMarketDataClient = Depends(get_binance_market_data_client),
) -> BinanceMarketPriceRead:
    price = await binance_client.fetch_latest_price(payload.symbol)
    event = market_data_service.set_price(payload.symbol, price, provider_name="binance")
    return BinanceMarketPriceRead(
        symbol=event.symbol,
        price=event.price,
        source="binance",
        updated_at=event.received_at,
    )


@router.post("/binance/candles", response_model=BinanceMarketCandlesRead)
async def fetch_binance_market_candles(
    payload: BinanceMarketCandlesRequest,
    db: DbSession,
    binance_client: BinanceMarketDataClient = Depends(get_binance_market_data_client),
) -> BinanceMarketCandlesRead:
    fetched_candles = await binance_client.fetch_candles(payload.symbol, payload.timeframe, payload.limit)
    service = get_market_candle_service(db)
    stored_candles = service.upsert_many(fetched_candles)
    return BinanceMarketCandlesRead(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        source="binance",
        requested_limit=payload.limit,
        stored_count=len(stored_candles),
        candles=[MarketCandleRead.model_validate(candle) for candle in stored_candles],
    )


@router.post("/candles", response_model=MarketCandleRead, status_code=status.HTTP_201_CREATED)
async def create_market_candle(payload: MarketCandleCreate, db: DbSession) -> MarketCandleRead:
    service = get_market_candle_service(db)
    candle = service.upsert(payload)
    return MarketCandleRead.model_validate(candle)


@router.get("/candles", response_model=list[MarketCandleRead])
async def list_market_candles(
    db: DbSession,
    symbol: str,
    timeframe: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[MarketCandleRead]:
    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip()
    if not normalized_symbol:
        raise HTTPException(status_code=422, detail="Symbol must not be empty")
    if not normalized_timeframe:
        raise HTTPException(status_code=422, detail="Timeframe must not be empty")
    service = get_market_candle_service(db)
    candles = service.list_recent(symbol=normalized_symbol, timeframe=normalized_timeframe, limit=limit)
    return [MarketCandleRead.model_validate(candle) for candle in candles]
