from decimal import Decimal, InvalidOperation

import httpx

from app.core.errors import AppError


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


async def fetch_latest_price(symbol: str, base_url: str) -> Decimal:
    return await BinanceMarketDataClient(base_url=base_url).fetch_latest_price(symbol)
