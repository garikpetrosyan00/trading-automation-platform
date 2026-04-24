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
from app.engine.bot_runner import BotRunner, RunnerConfig
from app.main import app as fastapi_app
from app.models.bot import Bot
from app.models.execution_profile import ExecutionProfile
from app.models.strategy import Strategy
from app.repositories.portfolio import PortfolioRepository
from app.services.portfolio_account import PortfolioAccountService
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
        event = MarketEvent(
            provider="stub",
            symbol=normalized_symbol,
            event_type=MarketEventType.TICKER,
            event_ts=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
            price=Decimal(price),
            close=Decimal(price),
        )
        self._latest_by_symbol[normalized_symbol] = event
        return event

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


@pytest.fixture
def bot_stack_factory():
    def create(
        session,
        *,
        name: str = "Threshold Bot",
        symbol: str = "BTCUSDT",
        status: str = "draft",
        cooldown_seconds: int = 60,
        description: str = "Test strategy",
    ) -> tuple[Strategy, Bot, ExecutionProfile]:
        strategy = Strategy(
            name=f"{name} Strategy",
            description=description,
            symbol=symbol,
            timeframe="1m",
            is_active=True,
        )
        session.add(strategy)
        session.commit()
        session.refresh(strategy)

        bot = Bot(
            name=name,
            strategy_id=strategy.id,
            exchange_name="binance",
            status=status,
            is_paper=True,
        )
        session.add(bot)
        session.commit()
        session.refresh(bot)

        profile = ExecutionProfile(
            bot_id=bot.id,
            max_position_size_usd=1000,
            max_daily_loss_usd=1000,
            max_open_positions=1,
            strategy_type="price_threshold",
            entry_below=Decimal("100"),
            exit_above=Decimal("110"),
            order_quantity=Decimal("0.1"),
            cooldown_seconds=cooldown_seconds,
            default_order_type="market",
            is_enabled=True,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return strategy, bot, profile

    return create


@pytest.fixture
def draft_bot(db_session, bot_stack_factory):
    _, bot, _ = bot_stack_factory(db_session)
    return bot


@pytest.fixture
def funded_account():
    def fund(session, *, currency: str = "USD", amount: Decimal = Decimal("1000")) -> None:
        PortfolioAccountService(PortfolioRepository(session)).ensure_account(currency, amount)

    return fund


@pytest.fixture
def set_latest_market_price(stub_market_data_service):
    def set_price(price: str, symbol: str = "BTCUSDT"):
        return stub_market_data_service.set_price(symbol, price)

    return set_price


@pytest.fixture
def bot_runner_factory(db_session_factory, stub_market_data_service):
    def create(*, market_data_service=None, clock=None) -> BotRunner:
        service = market_data_service or stub_market_data_service
        return BotRunner(
            session_factory=db_session_factory,
            market_data_service=service,
            config=RunnerConfig(
                enabled=True,
                poll_interval_seconds=3600,
                simulation_enabled=True,
                simulation_fee_bps=Decimal("0"),
                simulation_slippage_bps=Decimal("0"),
            ),
            now_provider=clock.now if clock is not None else None,
        )

    return create


@pytest.fixture
def configure_app_state(db_session_factory):
    def configure(*, market_data_service, bot_runner):
        fastapi_app.state.db_session_factory = db_session_factory
        fastapi_app.state.market_data_service = market_data_service
        fastapi_app.state.bot_runner = bot_runner
        return fastapi_app

    return configure
