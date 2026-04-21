import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.api.v1.endpoints.bots import list_bots as list_bots_endpoint
from app.api.v1.endpoints.bots import get_bot_summary as get_bot_summary_endpoint
from app.api.v1.endpoints.bot_runtime import pause_bot as pause_bot_endpoint
from app.api.v1.endpoints.bot_runtime import resume_bot as resume_bot_endpoint
from app.api.v1.endpoints.bot_runtime import run_bot_once as run_bot_once_endpoint
from app.api.v1.endpoints.market import set_market_price as set_market_price_endpoint
from app.core.errors import NotFoundError
from app.engine.bot_runner import BotRunner, RunnerConfig
from app.models.bot import Bot
from app.models.execution_profile import ExecutionProfile
from app.models.strategy import Strategy
from app.repositories.bot_run import BotRunRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.schemas.market import MarketPriceUpdateRequest
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


def create_named_bot_stack(
    db_session,
    name: str,
    symbol: str,
    status: str = "draft",
    cooldown_seconds: int = 60,
) -> tuple[Strategy, Bot, ExecutionProfile]:
    strategy = Strategy(
        name=f"{name} Strategy",
        description="Dashboard test strategy",
        symbol=symbol,
        timeframe="1m",
        is_active=True,
    )
    db_session.add(strategy)
    db_session.commit()
    db_session.refresh(strategy)

    bot = Bot(
        name=name,
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
    assert status.is_paused is False
    assert status.runner_enabled is True
    assert status.active_run_id is not None
    assert status.latest_price == Decimal("95")
    assert status.current_position_quantity == Decimal("0.10000000")
    assert status.cooldown_active is False
    assert status.last_event_message == "order_filled"
    assert len(bot_runs) == 1


def test_pause_endpoint_marks_bot_as_paused(db_session, db_session_factory, stub_market_data_service) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)

    response = asyncio.run(pause_bot_endpoint(bot.id, runner))
    status = runner.get_bot_status(bot.id)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.bot_id == bot.id
    assert response.status == "paused"
    assert response.is_paused is True
    assert status.bot_status == "paused"
    assert status.is_paused is True
    assert any(event.message == "bot_paused" for event in events)


def test_resume_endpoint_marks_bot_as_active_again(db_session, db_session_factory, stub_market_data_service) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    asyncio.run(pause_bot_endpoint(bot.id, runner))

    response = asyncio.run(resume_bot_endpoint(bot.id, runner))
    status = runner.get_bot_status(bot.id)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.bot_id == bot.id
    assert response.status == "active"
    assert response.is_paused is False
    assert status.bot_status == "active"
    assert status.is_paused is False
    assert any(event.message == "bot_resume_requested" for event in events)


def test_paused_bot_is_skipped_by_runner_and_does_not_place_buy_orders(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    asyncio.run(pause_bot_endpoint(bot.id, runner))
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert repository.list_orders() == []
    assert any(event.message == "bot_skipped_paused" for event in events)


def test_resumed_bot_can_trade_again(db_session, db_session_factory, stub_market_data_service) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    asyncio.run(pause_bot_endpoint(bot.id, runner))
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())

    asyncio.run(resume_bot_endpoint(bot.id, runner))
    asyncio.run(runner.run_cycle())

    orders = PortfolioRepository(db_session).list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert any(event.message == "bot_skipped_paused" for event in events)
    assert any(event.message == "bot_resume_requested" for event in events)
    assert any(event.message == "order_filled" for event in events)


def test_pause_resume_unknown_bot_returns_404(db_session_factory, stub_market_data_service) -> None:
    runner = build_runner(db_session_factory, stub_market_data_service)

    for endpoint in (pause_bot_endpoint, resume_bot_endpoint):
        try:
            asyncio.run(endpoint(999, runner))
        except NotFoundError as exc:
            assert exc.status_code == 404
            assert exc.error_code == "bot_not_found"
        else:
            raise AssertionError("Expected NotFoundError for unknown bot")


def test_bots_dashboard_returns_empty_list_when_no_bots(db_session_factory, stub_market_data_service) -> None:
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(list_bots_endpoint(runner))

    assert response.items == []


def test_bots_dashboard_returns_created_bots_in_deterministic_order(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    _, first_bot, _ = create_named_bot_stack(db_session, "BTC threshold bot", "BTCUSDT")
    _, second_bot, _ = create_named_bot_stack(db_session, "ETH threshold bot", "ETHUSDT")
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(list_bots_endpoint(runner))

    assert [item.bot_id for item in response.items] == [second_bot.id, first_bot.id]
    assert [item.name for item in response.items] == ["ETH threshold bot", "BTC threshold bot"]


def test_bots_dashboard_includes_paused_state(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    _, bot, _ = create_named_bot_stack(db_session, "Paused bot", "BTCUSDT", status="paused")
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(list_bots_endpoint(runner))

    item = response.items[0]
    assert item.bot_id == bot.id
    assert item.status == "paused"
    assert item.is_paused is True


def test_bots_dashboard_includes_cooldown_state_when_active(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_named_bot_stack(db_session, "Cooldown bot", "BTCUSDT", cooldown_seconds=60)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(runner.run_cycle())

    response = asyncio.run(list_bots_endpoint(runner))

    item = response.items[0]
    assert item.status == "active"
    assert item.cooldown_active is True
    assert item.cooldown_until is not None


def test_bots_dashboard_includes_current_position_quantity(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_named_bot_stack(db_session, "Position bot", "BTCUSDT")
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())

    response = asyncio.run(list_bots_endpoint(runner))

    assert response.items[0].current_position_qty == Decimal("0.10000000")
    assert response.items[0].last_price == Decimal("95")


def test_bots_dashboard_response_shape_stays_minimal_and_clean(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    create_named_bot_stack(db_session, "Shape bot", "BTCUSDT", status="paused")
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(list_bots_endpoint(runner))
    payload = response.model_dump()

    assert set(payload) == {"items"}
    assert set(payload["items"][0]) == {
        "bot_id",
        "name",
        "status",
        "is_paused",
        "strategy_type",
        "symbol",
        "cooldown_active",
        "cooldown_until",
        "current_position_qty",
        "last_price",
        "updated_at",
    }


def test_bot_summary_returns_404_for_unknown_bot(db_session_factory, stub_market_data_service) -> None:
    runner = build_runner(db_session_factory, stub_market_data_service)

    try:
        asyncio.run(get_bot_summary_endpoint(999, runner))
    except NotFoundError as exc:
        assert exc.status_code == 404
        assert exc.error_code == "bot_not_found"
    else:
        raise AssertionError("Expected NotFoundError for unknown bot")


def test_bot_summary_returns_existing_bot_summary(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    _, bot, _ = create_named_bot_stack(db_session, "BTC threshold bot", "BTCUSDT")
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(get_bot_summary_endpoint(bot.id, runner))

    assert response.bot_id == bot.id
    assert response.name == "BTC threshold bot"
    assert response.status == "draft"
    assert response.is_paused is False
    assert response.strategy_type == "price_threshold"
    assert response.symbol == "BTCUSDT"
    assert response.cooldown_seconds == 60
    assert response.buy_below_price == Decimal("100.00000000")
    assert response.sell_above_price == Decimal("110.00000000")
    assert response.recent_activity == []


def test_bot_summary_includes_paused_state_when_paused(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    _, bot, _ = create_named_bot_stack(db_session, "Paused summary bot", "BTCUSDT", status="paused")
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(get_bot_summary_endpoint(bot.id, runner))

    assert response.status == "paused"
    assert response.is_paused is True


def test_bot_summary_includes_cooldown_state_when_active(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_named_bot_stack(db_session, "Cooldown summary bot", "BTCUSDT", cooldown_seconds=60)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(runner.run_cycle())

    response = asyncio.run(get_bot_summary_endpoint(bot.id, runner))

    assert response.status == "active"
    assert response.cooldown_seconds == 60
    assert response.cooldown_active is True
    assert response.cooldown_until is not None


def test_bot_summary_includes_current_position_quantity(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_named_bot_stack(db_session, "Position summary bot", "BTCUSDT")
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())

    response = asyncio.run(get_bot_summary_endpoint(bot.id, runner))

    assert response.current_position_qty == Decimal("0.10000000")
    assert response.last_price == Decimal("95")


def test_bot_summary_includes_recent_activity_newest_first(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_named_bot_stack(db_session, "Activity summary bot", "BTCUSDT")
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(runner.run_cycle())

    response = asyncio.run(get_bot_summary_endpoint(bot.id, runner))

    messages = [item.message for item in response.recent_activity]
    assert messages[:4] == ["sell_filled", "sell_signal", "buy_filled", "buy_signal"]
    assert response.recent_activity[0].type == "order_filled"
    assert response.recent_activity[0].side == "sell"


def test_bot_summary_recent_activity_preview_is_capped(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_named_bot_stack(db_session, "Capped summary bot", "BTCUSDT", cooldown_seconds=1)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    for _ in range(6):
        stub_market_data_service.set_price("BTCUSDT", "95")
        asyncio.run(runner.run_cycle())
        stub_market_data_service.set_price("BTCUSDT", "115")
        asyncio.run(runner.run_cycle())

    response = asyncio.run(get_bot_summary_endpoint(bot.id, runner))

    assert len(response.recent_activity) == 10


def test_manual_bot_run_returns_404_for_unknown_bot(db_session_factory, stub_market_data_service) -> None:
    runner = build_runner(db_session_factory, stub_market_data_service)

    try:
        asyncio.run(run_bot_once_endpoint(999, runner))
    except NotFoundError as exc:
        assert exc.status_code == 404
        assert exc.error_code == "bot_not_found"
    else:
        raise AssertionError("Expected NotFoundError for unknown bot")


def test_manual_bot_run_paused_bot_returns_skipped_result(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    asyncio.run(pause_bot_endpoint(bot.id, runner))
    stub_market_data_service.set_price("BTCUSDT", "95")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    assert response.action == "skipped"
    assert response.message == "bot_skipped_paused"
    assert response.status == "paused"
    assert response.is_paused is True
    assert response.recent_activity_preview[0].message == "bot_skipped_paused"
    assert PortfolioRepository(db_session).list_orders() == []


def test_manual_bot_run_cooldown_active_returns_skipped_result(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session, cooldown_seconds=60)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(run_bot_once_endpoint(bot.id, runner))
    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(run_bot_once_endpoint(bot.id, runner))
    stub_market_data_service.set_price("BTCUSDT", "95")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    assert response.action == "skipped"
    assert response.message == "cooldown_active"
    assert response.cooldown_active is True
    assert response.cooldown_until is not None
    assert response.current_position_qty == Decimal("0E-8")
    assert response.recent_activity_preview[0].message == "cooldown_active"


def test_manual_bot_run_buy_eligible_returns_bought_result(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    assert response.action == "bought"
    assert response.message == "buy_filled"
    assert response.status == "active"
    assert response.is_paused is False
    assert response.current_position_qty == Decimal("0.10000000")
    assert response.last_price == Decimal("95")
    assert response.recent_activity_preview[0].message == "buy_filled"


def test_manual_bot_run_sell_eligible_returns_sold_result(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(run_bot_once_endpoint(bot.id, runner))
    stub_market_data_service.set_price("BTCUSDT", "115")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    assert response.action == "sold"
    assert response.message == "sell_filled"
    assert response.current_position_qty == Decimal("0E-8")
    assert response.last_price == Decimal("115")
    assert response.recent_activity_preview[0].message == "sell_filled"


def test_manual_bot_run_no_signal_returns_no_action(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "105")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    assert response.action == "no_action"
    assert response.message == "evaluation_no_signal"
    assert response.cooldown_active is False
    assert response.current_position_qty == Decimal("0")
    assert response.recent_activity_preview[0].message == "evaluation_no_signal"


def test_manual_bot_run_response_includes_consistent_bot_state_fields(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    payload = response.model_dump()

    assert set(payload) == {
        "bot_id",
        "status",
        "is_paused",
        "action",
        "message",
        "cooldown_active",
        "cooldown_until",
        "current_position_qty",
        "last_price",
        "recent_activity_preview",
    }
    assert response.bot_id == bot.id
    assert response.status == "active"
    assert response.cooldown_active is False
    assert len(response.recent_activity_preview) <= 3


def test_market_price_update_creates_price_for_new_symbol(stub_market_data_service) -> None:
    response = asyncio.run(
        set_market_price_endpoint(
            MarketPriceUpdateRequest(symbol="ethusdt", price=Decimal("95.00000000")),
            stub_market_data_service,
        )
    )
    latest = stub_market_data_service.get_latest("ETHUSDT")

    assert response.symbol == "ETHUSDT"
    assert response.price == Decimal("95.00000000")
    assert response.updated_at == latest.received_at
    assert latest.price == Decimal("95.00000000")


def test_market_price_update_updates_existing_symbol(stub_market_data_service) -> None:
    asyncio.run(
        set_market_price_endpoint(
            MarketPriceUpdateRequest(symbol="BTCUSDT", price=Decimal("95.00000000")),
            stub_market_data_service,
        )
    )

    response = asyncio.run(
        set_market_price_endpoint(
            MarketPriceUpdateRequest(symbol="btcusdt", price=Decimal("115.00000000")),
            stub_market_data_service,
        )
    )
    latest = stub_market_data_service.get_latest("BTCUSDT")

    assert response.symbol == "BTCUSDT"
    assert response.price == Decimal("115.00000000")
    assert latest.price == Decimal("115.00000000")


def test_market_price_update_rejects_zero_or_negative_price() -> None:
    for price in (Decimal("0"), Decimal("-1")):
        try:
            MarketPriceUpdateRequest(symbol="BTCUSDT", price=price)
        except ValueError:
            continue
        raise AssertionError("Expected validation error for non-positive price")


def test_market_price_update_is_used_by_manual_bot_run(
    db_session,
    db_session_factory,
    stub_market_data_service,
) -> None:
    PortfolioAccountService(PortfolioRepository(db_session)).ensure_account("USD", Decimal("1000"))
    _, bot, _ = create_bot_stack(db_session)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)

    asyncio.run(
        set_market_price_endpoint(
            MarketPriceUpdateRequest(symbol="btcusdt", price=Decimal("95.00000000")),
            stub_market_data_service,
        )
    )
    buy_response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    asyncio.run(
        set_market_price_endpoint(
            MarketPriceUpdateRequest(symbol="BTCUSDT", price=Decimal("115.00000000")),
            stub_market_data_service,
        )
    )
    sell_response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    assert buy_response.action == "bought"
    assert buy_response.last_price == Decimal("95.00000000")
    assert sell_response.action == "sold"
    assert sell_response.last_price == Decimal("115.00000000")


def test_market_price_update_response_shape_stays_small_and_clean(stub_market_data_service) -> None:
    response = asyncio.run(
        set_market_price_endpoint(
            MarketPriceUpdateRequest(symbol="BTCUSDT", price=Decimal("95.00000000")),
            stub_market_data_service,
        )
    )

    assert set(response.model_dump()) == {"symbol", "price", "updated_at"}
