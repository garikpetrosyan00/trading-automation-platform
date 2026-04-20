import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal

from app.data.providers.base import BaseMarketDataProvider
from app.data.schemas import MarketEvent, MarketEventType
from app.services.market_data_service import MarketDataService


class FakeMarketDataProvider(BaseMarketDataProvider):
    def __init__(self, symbol: str, events: list[MarketEvent]):
        super().__init__(symbol)
        self._events = events
        self.connected = False
        self.disconnected = False

    @property
    def name(self) -> str:
        return "fake"

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def stream_events(self) -> AsyncIterator[MarketEvent]:
        for event in self._events:
            yield event


def test_market_data_service_updates_latest_state() -> None:
    event = MarketEvent(
        provider="fake",
        symbol="BTCUSDT",
        event_type=MarketEventType.TICKER,
        event_ts=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
        price=Decimal("64000.00"),
        close=Decimal("64000.00"),
    )
    provider = FakeMarketDataProvider(symbol="BTCUSDT", events=[event])
    service = MarketDataService(provider=provider, enabled=True)

    async def run_service() -> None:
        await service.start()
        await asyncio.sleep(0)
        await service.stop()

    asyncio.run(run_service())

    status = service.get_status()
    latest = service.get_latest("BTCUSDT")

    assert provider.connected is True
    assert provider.disconnected is True
    assert status.enabled is True
    assert status.running is False
    assert status.provider == "fake"
    assert status.symbol == "BTCUSDT"
    assert status.received_event_count == 1
    assert latest is not None
    assert latest.symbol == "BTCUSDT"
    assert latest.price == Decimal("64000.00")


def test_market_data_service_returns_all_latest_events() -> None:
    event = MarketEvent(
        provider="fake",
        symbol="BTCUSDT",
        event_type=MarketEventType.TICKER,
        event_ts=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
        price=Decimal("64000.00"),
    )
    service = MarketDataService(provider=FakeMarketDataProvider("BTCUSDT", [event]), enabled=True)

    async def run_service() -> None:
        await service.start()
        await asyncio.sleep(0)
        await service.stop()

    asyncio.run(run_service())

    latest = service.get_latest()
    assert list(latest) == ["BTCUSDT"]
