from fastapi import APIRouter

from app.api.dependencies import MarketDataServiceDep
from app.schemas.market import MarketPriceRead, MarketPriceUpdateRequest

router = APIRouter(prefix="/market")


@router.post("/price", response_model=MarketPriceRead)
async def set_market_price(
    payload: MarketPriceUpdateRequest,
    market_data_service: MarketDataServiceDep,
) -> MarketPriceRead:
    event = market_data_service.set_price(payload.symbol, payload.price)
    return MarketPriceRead(symbol=event.symbol, price=event.price, updated_at=event.received_at)
