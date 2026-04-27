from fastapi import APIRouter, Depends

from app.api.dependencies import MarketDataServiceDep
from app.core.config import get_settings
from app.schemas.market import BinanceMarketPriceRead, MarketPriceRead, MarketPriceUpdateRequest, MarketSymbolRequest
from app.services.binance_market_data import BinanceMarketDataClient

router = APIRouter(prefix="/market")


def get_binance_market_data_client() -> BinanceMarketDataClient:
    settings = get_settings()
    return BinanceMarketDataClient(base_url=settings.binance_market_data_base_url)


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
