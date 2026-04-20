from datetime import datetime, timezone
from decimal import Decimal

from app.data.providers.base import BaseMarketDataProvider
from app.data.schemas import MarketEvent, MarketEventType
from app.db.base import Base
from app.main import app
from app.services.market_data_service import MarketDataService


class EmptyProvider(BaseMarketDataProvider):
    @property
    def name(self) -> str:
        return "fake"

    async def stream_events(self):
        if False:
            yield


def test_market_data_status_and_latest_endpoints(db_session_factory, noop_bot_runner) -> None:
    service = MarketDataService(provider=EmptyProvider(symbol="BTCUSDT"), enabled=False)
    service._latest_by_symbol["BTCUSDT"] = MarketEvent(
        provider="fake",
        symbol="BTCUSDT",
        event_type=MarketEventType.TICKER,
        event_ts=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
        price=Decimal("64000.00"),
        close=Decimal("64000.00"),
    )
    service._received_event_count = 1
    service._last_received_at = datetime(2026, 4, 20, 12, 0, 1, tzinfo=timezone.utc)
    app.state.market_data_service = service
    app.state.db_session_factory = db_session_factory
    app.state.bot_runner = noop_bot_runner

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        status_response = client.get("/api/v1/market-data/status")
        latest_response = client.get("/api/v1/market-data/latest")
        symbol_response = client.get("/api/v1/market-data/latest", params={"symbol": "btcusdt"})

    assert status_response.status_code == 200
    assert status_response.json() == {
        "running": False,
        "enabled": False,
        "provider": "fake",
        "symbol": "BTCUSDT",
        "last_received_event_ts": "2026-04-20T12:00:00Z",
        "last_received_at": "2026-04-20T12:00:01Z",
        "received_event_count": 1,
    }

    assert latest_response.status_code == 200
    assert latest_response.json() == {
        "symbol": None,
        "latest": {
            "BTCUSDT": {
                "provider": "fake",
                "symbol": "BTCUSDT",
                "event_type": "ticker",
                "event_ts": "2026-04-20T12:00:00Z",
                "received_at": latest_response.json()["latest"]["BTCUSDT"]["received_at"],
                "price": "64000.00",
                "bid": None,
                "ask": None,
                "open": None,
                "high": None,
                "low": None,
                "close": "64000.00",
                "volume": None,
                "raw_payload": None,
            }
        },
    }

    assert symbol_response.status_code == 200
    assert symbol_response.json() == {
        "symbol": "BTCUSDT",
        "latest": {
            "provider": "fake",
            "symbol": "BTCUSDT",
            "event_type": "ticker",
            "event_ts": "2026-04-20T12:00:00Z",
            "received_at": symbol_response.json()["latest"]["received_at"],
            "price": "64000.00",
            "bid": None,
            "ask": None,
            "open": None,
            "high": None,
            "low": None,
            "close": "64000.00",
            "volume": None,
            "raw_payload": None,
        },
    }
