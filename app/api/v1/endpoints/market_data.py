from fastapi import APIRouter, Query

from app.api.dependencies import MarketDataServiceDep
from app.data.schemas import MarketDataLatestResponse, MarketDataStatus

router = APIRouter(prefix="/market-data")


@router.get("/status", response_model=MarketDataStatus)
async def market_data_status(market_data_service: MarketDataServiceDep) -> MarketDataStatus:
    return market_data_service.get_status()


@router.get("/latest", response_model=MarketDataLatestResponse)
async def market_data_latest(
    market_data_service: MarketDataServiceDep,
    symbol: str | None = Query(default=None),
) -> MarketDataLatestResponse:
    normalized_symbol = symbol.upper() if symbol else None
    latest = market_data_service.get_latest(normalized_symbol)
    return MarketDataLatestResponse(symbol=normalized_symbol, latest=latest or {})
