from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from app.core.errors import AppError
from app.schemas.market import MarketCandleCreate


class BinanceMarketDataError(AppError):
    status_code = 502
    error_code = "binance_market_data_error"


class BinanceMarketDataClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def fetch_latest_price(self, symbol: str) -> Decimal:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise BinanceMarketDataError("Symbol must not be empty", status_code=422, error_code="invalid_symbol")

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get("/api/v3/ticker/price", params={"symbol": normalized_symbol})
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise BinanceMarketDataError("Could not reach Binance market data") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise BinanceMarketDataError(
                f"Binance market data request failed with status {response.status_code}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceMarketDataError("Binance market data returned invalid JSON") from exc

        raw_price = payload.get("price") if isinstance(payload, dict) else None
        try:
            price = Decimal(str(raw_price))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise BinanceMarketDataError("Binance market data returned an invalid price") from exc

        if not price.is_finite() or price <= Decimal("0"):
            raise BinanceMarketDataError("Binance market data returned an invalid price")

        return price

    async def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> list[MarketCandleCreate]:
        normalized_symbol = symbol.strip().upper()
        normalized_timeframe = timeframe.strip()
        if not normalized_symbol:
            raise BinanceMarketDataError("Symbol must not be empty", status_code=422, error_code="invalid_symbol")
        if not normalized_timeframe:
            raise BinanceMarketDataError("Timeframe must not be empty", status_code=422, error_code="invalid_timeframe")
        if limit < 1 or limit > 500:
            raise BinanceMarketDataError("Limit must be between 1 and 500", status_code=422, error_code="invalid_limit")

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    "/api/v3/klines",
                    params={"symbol": normalized_symbol, "interval": normalized_timeframe, "limit": limit},
                )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise BinanceMarketDataError("Could not reach Binance market data") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise BinanceMarketDataError(
                f"Binance market data request failed with status {response.status_code}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceMarketDataError("Binance market data returned invalid JSON") from exc

        if not isinstance(payload, list):
            raise BinanceMarketDataError("Binance market data returned invalid candle data")

        return [
            self._parse_kline(normalized_symbol, normalized_timeframe, item)
            for item in payload
        ]

    @staticmethod
    def _parse_kline(symbol: str, timeframe: str, item) -> MarketCandleCreate:
        if not isinstance(item, list) or len(item) < 7:
            raise BinanceMarketDataError("Binance market data returned invalid candle data")

        try:
            open_time = datetime.fromtimestamp(int(item[0]) / 1000, tz=timezone.utc)
            close_time = datetime.fromtimestamp(int(item[6]) / 1000, tz=timezone.utc)
            candle = MarketCandleCreate(
                symbol=symbol,
                timeframe=timeframe,
                open_time=open_time,
                close_time=close_time,
                open_price=item[1],
                high_price=item[2],
                low_price=item[3],
                close_price=item[4],
                volume=item[5],
                source="binance",
            )
        except (TypeError, ValueError, OverflowError, ValidationError) as exc:
            raise BinanceMarketDataError("Binance market data returned invalid candle data") from exc

        return candle


async def fetch_latest_price(symbol: str, base_url: str) -> Decimal:
    return await BinanceMarketDataClient(base_url=base_url).fetch_latest_price(symbol)
