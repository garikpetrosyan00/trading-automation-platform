from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from decimal import Decimal

from app.core.logging import get_logger
from app.data.providers.base import BaseMarketDataProvider
from app.data.providers.binance import BinanceMarketDataProvider
from app.data.schemas import MarketDataProviderName, MarketDataStatus, MarketEvent, MarketEventType

logger = get_logger(__name__)


class MarketDataService:
    def __init__(self, provider: BaseMarketDataProvider, enabled: bool = True):
        self.provider = provider
        self.enabled = enabled
        self._task: asyncio.Task[None] | None = None
        self._latest_by_symbol: dict[str, MarketEvent] = {}
        self._received_event_count = 0
        self._last_received_at: datetime | None = None

    @classmethod
    def from_settings(cls, settings) -> "MarketDataService":
        provider_name = settings.market_data_provider.lower()
        if provider_name != MarketDataProviderName.BINANCE.value:
            raise ValueError(f"Unsupported market data provider: {settings.market_data_provider}")

        provider = BinanceMarketDataProvider(
            symbol=settings.market_data_symbol,
            websocket_url=settings.market_data_websocket_url,
            reconnect_delay_seconds=settings.market_data_reconnect_delay_seconds,
            include_raw_payload=settings.market_data_include_raw_payload,
        )
        return cls(provider=provider, enabled=settings.market_data_enabled)

    async def start(self) -> None:
        if not self.enabled:
            logger.info(
                "market_data_disabled",
                extra={"provider": self.provider.name, "symbol": self.provider.symbol},
            )
            return

        if self._task is not None and not self._task.done():
            return

        logger.info(
            "market_data_service_starting",
            extra={"provider": self.provider.name, "symbol": self.provider.symbol},
        )
        self._task = asyncio.create_task(self._run(), name="market-data-service")

    async def stop(self) -> None:
        task = self._task
        self._task = None

        if task is None:
            return

        logger.info(
            "market_data_service_stopping",
            extra={"provider": self.provider.name, "symbol": self.provider.symbol},
        )
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _run(self) -> None:
        await self.provider.connect()
        try:
            async for event in self.provider.stream_events():
                self._latest_by_symbol[event.symbol] = event
                self._received_event_count += 1
                self._last_received_at = datetime.now(timezone.utc)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "market_data_service_consumer_error",
                extra={"provider": self.provider.name, "symbol": self.provider.symbol},
            )
        finally:
            await self.provider.disconnect()

    def get_status(self) -> MarketDataStatus:
        latest = self._latest_by_symbol.get(self.provider.symbol)
        running = self._task is not None and not self._task.done()
        return MarketDataStatus(
            running=running,
            enabled=self.enabled,
            provider=self.provider.name,
            symbol=self.provider.symbol,
            last_received_event_ts=latest.event_ts if latest else None,
            last_received_at=self._last_received_at,
            received_event_count=self._received_event_count,
        )

    def get_latest(self, symbol: str | None = None) -> MarketEvent | dict[str, MarketEvent]:
        if symbol is None:
            return dict(self._latest_by_symbol)
        return self._latest_by_symbol.get(symbol.upper())

    def set_price(self, symbol: str, price: Decimal, provider_name: str | None = None) -> MarketEvent:
        now = datetime.now(timezone.utc)
        normalized_symbol = symbol.strip().upper()
        event = MarketEvent(
            provider=provider_name or self.provider.name,
            symbol=normalized_symbol,
            event_type=MarketEventType.TICKER,
            event_ts=now,
            received_at=now,
            price=price,
            close=price,
        )
        self._latest_by_symbol[normalized_symbol] = event
        self._received_event_count += 1
        self._last_received_at = now
        return event
