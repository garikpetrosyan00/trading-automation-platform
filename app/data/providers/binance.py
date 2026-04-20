from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import websockets

from app.core.logging import get_logger
from app.data.providers.base import BaseMarketDataProvider
from app.data.schemas import MarketEvent, MarketEventType

logger = get_logger(__name__)


class BinanceMarketDataProvider(BaseMarketDataProvider):
    def __init__(
        self,
        symbol: str,
        websocket_url: str,
        reconnect_delay_seconds: float = 2.0,
        include_raw_payload: bool = False,
    ):
        super().__init__(symbol=symbol)
        self.websocket_url = websocket_url.rstrip("/")
        self.reconnect_delay_seconds = reconnect_delay_seconds
        self.include_raw_payload = include_raw_payload

    @property
    def name(self) -> str:
        return "binance"

    @property
    def stream_url(self) -> str:
        return f"{self.websocket_url}/{self.symbol.lower()}@ticker"

    async def stream_events(self) -> AsyncIterator[MarketEvent]:
        while True:
            try:
                logger.info(
                    "market_data_provider_connecting",
                    extra={"provider": self.name, "symbol": self.symbol, "url": self.stream_url},
                )
                async with websockets.connect(self.stream_url) as websocket:
                    logger.info(
                        "market_data_provider_connected",
                        extra={"provider": self.name, "symbol": self.symbol},
                    )
                    async for message in websocket:
                        try:
                            yield self.parse_message(message)
                        except ValueError:
                            logger.exception(
                                "market_data_provider_parse_failure",
                                extra={"provider": self.name, "symbol": self.symbol},
                            )
            except asyncio.CancelledError:
                logger.info(
                    "market_data_provider_cancelled",
                    extra={"provider": self.name, "symbol": self.symbol},
                )
                raise
            except Exception:
                logger.exception(
                    "market_data_provider_stream_error",
                    extra={"provider": self.name, "symbol": self.symbol},
                )
                logger.info(
                    "market_data_provider_reconnecting",
                    extra={
                        "provider": self.name,
                        "symbol": self.symbol,
                        "reconnect_delay_seconds": self.reconnect_delay_seconds,
                    },
                )
                await asyncio.sleep(self.reconnect_delay_seconds)

    def parse_message(self, message: str) -> MarketEvent:
        payload = json.loads(message)
        return self.parse_payload(payload)

    def parse_payload(self, payload: dict[str, Any]) -> MarketEvent:
        try:
            event_time = datetime.fromtimestamp(payload["E"] / 1000, tz=timezone.utc)
            return MarketEvent(
                provider=self.name,
                symbol=str(payload["s"]).upper(),
                event_type=MarketEventType.TICKER,
                event_ts=event_time,
                price=self._to_decimal(payload.get("c")),
                bid=self._to_decimal(payload.get("b")),
                ask=self._to_decimal(payload.get("a")),
                open=self._to_decimal(payload.get("o")),
                high=self._to_decimal(payload.get("h")),
                low=self._to_decimal(payload.get("l")),
                close=self._to_decimal(payload.get("c")),
                volume=self._to_decimal(payload.get("v")),
                raw_payload=payload if self.include_raw_payload else None,
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise ValueError("Invalid Binance ticker payload") from exc

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))
