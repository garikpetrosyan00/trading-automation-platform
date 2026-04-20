import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.data.schemas import MarketEvent, MarketEventType
from app.db.base import Base
from app.main import app
from datetime import datetime, timezone
from decimal import Decimal

import app.models  # noqa: F401


class StubMarketDataService:
    def __init__(self):
        self._latest_by_symbol: dict[str, MarketEvent] = {}

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def set_price(self, symbol: str, price: str) -> None:
        normalized_symbol = symbol.upper()
        self._latest_by_symbol[normalized_symbol] = MarketEvent(
            provider="stub",
            symbol=normalized_symbol,
            event_type=MarketEventType.TICKER,
            event_ts=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
            price=Decimal(price),
            close=Decimal(price),
        )

    def get_latest(self, symbol: str | None = None):
        if symbol is None:
            return dict(self._latest_by_symbol)
        return self._latest_by_symbol.get(symbol.upper())

    def get_status(self):
        return {
            "running": False,
            "enabled": True,
            "provider": "stub",
            "symbol": next(iter(self._latest_by_symbol), "BTCUSDT"),
            "last_received_event_ts": None,
            "last_received_at": None,
            "received_event_count": len(self._latest_by_symbol),
        }


class NoopBotRunner:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    yield TestingSessionLocal
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_session_factory):
    with db_session_factory() as session:
        yield session


@pytest.fixture
def stub_market_data_service():
    return StubMarketDataService()


@pytest.fixture
def noop_bot_runner():
    return NoopBotRunner()
