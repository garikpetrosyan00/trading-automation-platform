import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.engine.bot_runner import BotRunner, RunnerConfig
from app.models.bot import Bot
from app.models.execution_profile import ExecutionProfile
from app.models.strategy import Strategy
from app.repositories.bot_run import BotRunRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.services.portfolio_account import PortfolioAccountService


def create_bot_stack(db_session, status: str = "draft", cooldown_seconds: int = 60) -> tuple[Strategy, Bot, ExecutionProfile]:
    strategy = Strategy(
        name="Threshold Strategy",
        description="First rule-based bot",
        symbol="BTCUSDT",
        timeframe="1m",
        is_active=True,
    )
    db_session.add(strategy)
    db_session.commit()
    db_session.refresh(strategy)

    bot = Bot(
        name="Threshold Bot",
        strategy_id=strategy.id,
        exchange_name="binance",
        status=status,
        is_paper=True,
    )
    db_session.add(bot)
    db_session.commit()
    db_session.refresh(bot)

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
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return strategy, bot, profile


class FakeClock:
    def __init__(self):
        self.current = datetime.now(timezone.utc)

    def now(self):
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


def build_runner(db_session_factory, stub_market_data_service, clock: FakeClock | None = None) -> BotRunner:
    return BotRunner(
        session_factory=db_session_factory,
        market_data_service=stub_market_data_service,
        config=RunnerConfig(
            enabled=True,
            poll_interval_seconds=3600,
            simulation_enabled=True,
            simulation_fee_bps=Decimal("0"),
            simulation_slippage_bps=Decimal("0"),
        ),
        now_provider=clock.now if clock is not None else None,
    )


def test_bot_start_and_stop(db_session, db_session_factory, stub_market_data_service) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)

    start_status = runner.start_bot(bot.id)
    stop_status = runner.stop_bot(bot.id)

    assert start_status.bot_status == "active"
    assert start_status.active_run_id is not None
    assert start_status.active_run_status == "running"
    assert start_status.cooldown_active is False
    assert stop_status.bot_status == "paused"
    assert stop_status.active_run_id is None
    assert stop_status.active_run_status is None


def test_no_buy_when_latest_price_missing(db_session, db_session_factory, stub_market_data_service) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)

    asyncio.run(runner.run_cycle())

    orders = PortfolioRepository(db_session).list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert orders == []
    assert any(event.message == "evaluation_skipped" for event in events)


def test_buy_signal_triggers_one_buy_and_no_duplicate_buy(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())
    asyncio.run(runner.run_cycle())

    repository = PortfolioRepository(db_session)
    orders = repository.list_orders()
    position = repository.get_position_by_symbol("BTCUSDT")

    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert position is not None
    assert position.quantity == Decimal("0.10000000")


def test_sell_signal_triggers_full_sell(db_session, db_session_factory, stub_market_data_service) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())

    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(runner.run_cycle())

    repository = PortfolioRepository(db_session)
    orders = repository.list_orders()
    fills = repository.list_fills()
    position = repository.get_position_by_symbol("BTCUSDT")
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert len(orders) == 2
    assert orders[0].side == "sell"
    assert orders[1].side == "buy"
    assert len(fills) == 2
    assert position is not None
    assert position.quantity == Decimal("0E-8")
    assert any(event.message == "buy_signal" for event in events)
    assert any(event.message == "sell_signal" for event in events)
    assert sum(1 for event in events if event.message == "order_filled") == 2


def test_bot_does_not_rebuy_during_cooldown(db_session, db_session_factory, stub_market_data_service) -> None:
    clock = FakeClock()
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session, cooldown_seconds=60)
    runner = build_runner(db_session_factory, stub_market_data_service, clock=clock)
    runner.start_bot(bot.id)

    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())

    repository = PortfolioRepository(db_session)
    orders = repository.list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)
    status = runner.get_bot_status(bot.id)

    assert len(orders) == 2
    assert orders[0].side == "sell"
    assert orders[1].side == "buy"
    assert any(event.message == "cooldown_active" for event in events)
    assert status.cooldown_active is True
    assert status.current_position_quantity == Decimal("0E-8")


def test_bot_can_buy_again_after_cooldown_expires(db_session, db_session_factory, stub_market_data_service) -> None:
    clock = FakeClock()
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session, cooldown_seconds=60)
    runner = build_runner(db_session_factory, stub_market_data_service, clock=clock)
    runner.start_bot(bot.id)

    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    clock.advance(61)
    asyncio.run(runner.run_cycle())

    repository = PortfolioRepository(db_session)
    orders = repository.list_orders()
    status = runner.get_bot_status(bot.id)

    assert len(orders) == 3
    assert orders[0].side == "buy"
    assert orders[1].side == "sell"
    assert orders[2].side == "buy"
    assert status.cooldown_active is False


def test_status_reflects_current_state(db_session, db_session_factory, stub_market_data_service) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())

    status = runner.get_bot_status(bot.id)
    bot_runs = BotRunRepository(db_session).list_for_bot(bot.id)

    assert status.bot_status == "active"
    assert status.runner_enabled is True
    assert status.active_run_id is not None
    assert status.latest_price == Decimal("95")
    assert status.current_position_quantity == Decimal("0.10000000")
    assert status.cooldown_active is False
    assert status.last_event_message == "order_filled"
    assert len(bot_runs) == 1
