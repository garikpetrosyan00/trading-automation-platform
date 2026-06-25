import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text

from app.api.v1.endpoints.bots import list_bots as list_bots_endpoint
from app.api.v1.endpoints.bots import get_bot_summary as get_bot_summary_endpoint
from app.api.v1.endpoints.bot_runtime import pause_bot as pause_bot_endpoint
from app.api.v1.endpoints.bot_runtime import resume_bot as resume_bot_endpoint
from app.api.v1.endpoints.bot_runtime import run_bot_once as run_bot_once_endpoint
from app.api.v1.endpoints.bot_runtime import list_run_events as list_run_events_endpoint
from app.api.v1.endpoints.market import set_market_price as set_market_price_endpoint
from app.core.errors import NotFoundError
from app.engine.bot_runner import BotRunner, RunnerConfig
from app.models.market_candle import MarketCandle
from app.models.paper_position import PaperPosition
from app.models.position import Position
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.schemas.market import MarketPriceUpdateRequest
from app.services.draft_balance import DraftBalanceService


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


def reset_draft_balance(
    session,
    bot_id: int,
    defaults: dict[str, tuple[Decimal, Decimal]] | None = None,
) -> None:
    DraftBalanceService(DraftBalanceRepository(session), BotRepository(session)).reset_bot_draft_balance(
        bot_id,
        defaults=defaults,
    )


def reset_draft_balance_with_base(session, bot_id: int, asset: str, quantity: Decimal) -> None:
    reset_draft_balance(
        session,
        bot_id,
        defaults={
            "USDT": (Decimal("10000"), Decimal("0")),
            asset: (quantity, Decimal("0")),
        },
    )


def seed_open_position(
    session,
    *,
    bot_id: int,
    symbol: str,
    base_asset: str,
    quote_asset: str,
    quantity: Decimal,
    average_entry_price: Decimal,
) -> None:
    session.add_all(
        [
            Position(
                symbol=symbol,
                quantity=quantity,
                average_entry_price=average_entry_price,
                realized_pnl=Decimal("0"),
            ),
            PaperPosition(
                bot_id=bot_id,
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                quantity=quantity,
                average_entry_price=average_entry_price,
                realized_pnl=Decimal("0"),
            ),
        ]
    )


def add_candles(
    session,
    *,
    symbol: str = "BTCUSDT",
    timeframe: str = "1m",
    closes: list[str],
    source: str = "manual",
) -> None:
    start = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)
    for index, close in enumerate(closes):
        close_price = Decimal(close)
        open_time = start + timedelta(minutes=index)
        candle = MarketCandle(
            symbol=symbol,
            timeframe=timeframe,
            open_time=open_time,
            close_time=open_time + timedelta(minutes=1),
            open_price=close_price,
            high_price=close_price,
            low_price=close_price,
            close_price=close_price,
            volume=Decimal("1"),
            source=source,
        )
        session.add(candle)
    session.commit()


def configure_moving_average_strategy(strategy, *, short_window: str = "2", long_window: str = "3", quantity: str = "0.1") -> None:
    strategy.strategy_type = "moving_average_cross"
    strategy.parameters = {
        "short_window": short_window,
        "long_window": long_window,
        "quantity": quantity,
    }


def configure_macd_crossover_strategy(
    strategy,
    *,
    fast_period: str = "2",
    slow_period: str = "3",
    signal_period: str = "2",
    quantity: str = "0.1",
) -> None:
    strategy.strategy_type = "macd_crossover"
    strategy.parameters = {
        "fast_period": fast_period,
        "slow_period": slow_period,
        "signal_period": signal_period,
        "quantity": quantity,
    }


def configure_rsi_threshold_strategy(
    strategy,
    *,
    period: str = "2",
    oversold: str = "30",
    overbought: str = "70",
    quantity: str = "0.1",
) -> None:
    strategy.strategy_type = "rsi_threshold"
    strategy.parameters = {
        "period": period,
        "oversold": oversold,
        "overbought": overbought,
        "quantity": quantity,
    }


def configure_bollinger_bands_strategy(
    strategy,
    *,
    period: str = "3",
    stddev_multiplier: str = "0.5",
    quantity: str = "0.1",
) -> None:
    strategy.strategy_type = "bollinger_bands"
    strategy.parameters = {
        "period": period,
        "stddev_multiplier": stddev_multiplier,
        "quantity": quantity,
    }


def test_bot_start_and_stop(db_session, db_session_factory, stub_market_data_service, bot_stack_factory, funded_account) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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


def test_background_missing_price_does_not_record_skipped_activity_noise(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)

    asyncio.run(runner.run_cycle())
    asyncio.run(runner.run_cycle())
    asyncio.run(runner.run_cycle())

    orders = PortfolioRepository(db_session).list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert orders == []
    assert [event.message for event in events].count("evaluation_skipped") == 0


def test_buy_signal_triggers_one_buy_and_no_duplicate_buy(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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
    assert orders[0].bot_id == bot.id
    assert orders[0].strategy_id == bot.strategy_id
    assert orders[0].order_type == "market"
    assert orders[0].status == "filled"
    assert orders[0].mode == "paper"
    assert orders[0].decision_reason == "price is below strategy buy_below"
    assert position is not None
    assert position.quantity == Decimal("0.10000000")


def test_runtime_risk_blocks_buy_when_max_trade_quantity_is_exceeded(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, profile = bot_stack_factory(db_session)
    assert profile is not None
    reset_draft_balance(db_session, bot.id)
    profile.max_trade_quantity = Decimal("0.05")
    db_session.add(profile)
    db_session.commit()

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    orders = PortfolioRepository(db_session).list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert orders == []
    blocked_event = next(event for event in events if event.message == "risk_limit_blocked")
    assert blocked_event.payload["reason"] == "max_trade_quantity_exceeded"
    assert blocked_event.payload["decision"] == "skipped"
    assert blocked_event.payload["risk"]["max_trade_quantity"] == "0.05000000"


def test_runtime_risk_blocks_buy_when_max_position_quantity_is_exceeded(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, profile = bot_stack_factory(db_session)
    assert profile is not None
    reset_draft_balance(db_session, bot.id)
    profile.max_position_quantity = Decimal("0.05")
    db_session.add(profile)
    db_session.commit()

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    orders = PortfolioRepository(db_session).list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert orders == []
    blocked_event = next(event for event in events if event.message == "risk_limit_blocked")
    assert blocked_event.payload["reason"] == "max_position_quantity_exceeded"
    assert blocked_event.payload["risk"]["requested_position_quantity"] == "0.10000000"
    assert blocked_event.payload["risk"]["max_position_quantity"] == "0.05000000"


def test_runtime_null_risk_fields_preserve_existing_buy_behavior(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, profile = bot_stack_factory(db_session)
    assert profile is not None
    reset_draft_balance(db_session, bot.id)
    assert profile.max_trade_quantity is None
    assert profile.max_position_quantity is None
    assert profile.stop_loss_percent is None

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    orders = PortfolioRepository(db_session).list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert not any(event.message == "risk_limit_blocked" for event in events)


def test_sell_signal_triggers_full_sell(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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
    assert fills[0].order_id == orders[0].id
    assert fills[0].fill_quantity == orders[0].quantity
    assert fills[0].source == "paper"
    assert position is not None
    assert position.quantity == Decimal("0E-8")
    assert any(event.message == "buy_signal" for event in events)
    assert any(event.message == "sell_signal" for event in events)
    assert sum(1 for event in events if event.message == "order_filled") == 2


def test_bot_runner_allows_sell_exit_after_daily_count_exhausted(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    runner = BotRunner(
        session_factory=db_session_factory,
        market_data_service=stub_market_data_service,
        config=RunnerConfig(
            enabled=True,
            poll_interval_seconds=3600,
            simulation_enabled=True,
            simulation_fee_bps=Decimal("0"),
            simulation_slippage_bps=Decimal("0"),
            execution_max_daily_order_count=1,
        ),
    )
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())

    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(runner.run_cycle())

    repository = PortfolioRepository(db_session)
    orders = repository.list_orders()
    position = repository.get_position_by_symbol("BTCUSDT")
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    assert [order.side for order in orders] == ["sell", "buy"]
    assert position is not None
    assert position.quantity == Decimal("0E-8")
    assert [attempt.final_status for attempt in attempts] == ["filled", "filled"]
    assert attempts[0].side == "sell"
    assert attempts[0].metadata_["risk_reducing_exit"] is True


def test_live_mode_records_not_implemented_without_order(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, is_paper=False)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    orders = PortfolioRepository(db_session).list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert orders == []
    live_event = next(event for event in events if event.message == "live_mode_not_implemented")
    assert live_event.payload["side"] == "buy"
    assert live_event.payload["symbol"] == "BTCUSDT"


def test_buy_decision_and_quantity_use_strategy_parameters(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, profile = bot_stack_factory(db_session)
    assert profile is not None
    reset_draft_balance(db_session, bot.id)
    strategy.parameters = {
        "buy_below": "100",
        "sell_above": "110",
        "quantity": "0.2",
    }
    profile.entry_below = Decimal("90")
    profile.order_quantity = Decimal("0.1")
    db_session.add_all([strategy, profile])
    db_session.commit()

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    repository = PortfolioRepository(db_session)
    orders = repository.list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].quantity == Decimal("0.20000000")
    assert any(event.message == "order_filled" for event in events)
    buy_signal = next(event for event in events if event.message == "buy_signal")
    assert buy_signal.payload["detail"] == "price is below strategy buy_below"
    assert buy_signal.payload["quantity"] == "0.2"


def test_sell_decision_uses_strategy_parameters_sell_above(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, profile = bot_stack_factory(db_session)
    assert profile is not None
    reset_draft_balance(db_session, bot.id)
    strategy.parameters = {
        "buy_below": "100",
        "sell_above": "110",
        "quantity": "0.2",
    }
    profile.exit_above = Decimal("120")
    db_session.add_all([strategy, profile])
    db_session.commit()

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "115")

    asyncio.run(runner.run_cycle())

    orders = PortfolioRepository(db_session).list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert len(orders) == 2
    assert orders[0].side == "sell"
    assert orders[0].quantity == Decimal("0.20000000")
    sell_signal = next(event for event in events if event.message == "sell_signal")
    assert sell_signal.payload["detail"] == "price is above strategy sell_above and position exists"


def test_missing_strategy_parameters_fall_back_to_execution_profile_fields(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    strategy.parameters = {}
    db_session.add(strategy)
    db_session.commit()

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    orders = PortfolioRepository(db_session).list_orders()

    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].quantity == Decimal("0.10000000")


def test_invalid_strategy_parameter_is_safe_skipped_evaluation(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    strategy.parameters = {
        "buy_below": "not-a-number",
        "sell_above": "110",
        "quantity": "0.1",
    }
    db_session.add(strategy)
    db_session.commit()

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["reason"] == "invalid_strategy_parameter"
    assert skipped_event.payload["parameter"] == "buy_below"


def test_missing_strategy_type_falls_back_to_price_threshold() -> None:
    class LegacyStrategy:
        strategy_type = None

    assert BotRunner._strategy_type(LegacyStrategy()) == "price_threshold"


def test_unsupported_strategy_type_is_skipped_without_orders_or_position(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    db_session.execute(text("PRAGMA ignore_check_constraints = ON"))
    db_session.execute(
        text("UPDATE strategies SET strategy_type = :strategy_type WHERE id = :strategy_id"),
        {"strategy_type": "rsi", "strategy_id": strategy.id},
    )
    db_session.commit()

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "unsupported_strategy_type"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "unsupported strategy type: rsi"
    assert repository.list_orders() == []
    assert repository.get_position_by_symbol("BTCUSDT") is None

    unsupported_event = next(event for event in events if event.message == "unsupported_strategy_type")
    assert unsupported_event.payload["strategy_type"] == "rsi"
    assert unsupported_event.payload["reason"] == "unsupported strategy type: rsi"


def test_moving_average_cross_buy_crossover_creates_buy_paper_order(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_moving_average_strategy(strategy)
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "10", "10", "20"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "20")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "bought"
    assert response.message == "buy_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "buy"
    assert response.decision_explanation.reason == "short moving average crossed above long moving average"
    assert response.decision_explanation.short_window == 2
    assert response.decision_explanation.long_window == 3
    assert response.decision_explanation.previous_short_ma == Decimal("10.00000000")
    assert response.decision_explanation.current_short_ma == Decimal("15.00000000")
    assert response.decision_explanation.candles_used == 4
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].quantity == Decimal("0.10000000")
    assert repository.get_position_by_symbol("BTCUSDT") is not None

    buy_signal = next(event for event in events if event.message == "buy_signal")
    assert buy_signal.payload["strategy_type"] == "moving_average_cross"
    assert buy_signal.payload["previous_long_ma"] == "10.00000000"
    assert buy_signal.payload["current_long_ma"] == "13.33333333"


def test_moving_average_cross_uses_configured_candle_source(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_moving_average_strategy(strategy)
    strategy.parameters["candle_source"] = "binance"
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "11", "12", "13"], source="manual")
    add_candles(db_session, closes=["10", "10", "10", "20"], source="binance")

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "20")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "bought"
    buy_signal = next(event for event in events if event.message == "buy_signal")
    assert buy_signal.payload["candle_source"] == "binance"
    assert buy_signal.payload["current_long_ma"] == "13.33333333"


def test_moving_average_cross_missing_quantity_uses_execution_profile_quantity(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, profile = bot_stack_factory(db_session)
    assert profile is not None
    reset_draft_balance(db_session, bot.id)
    reset_draft_balance(db_session, bot.id)
    configure_moving_average_strategy(strategy)
    strategy.parameters.pop("quantity")
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "10", "10", "20"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "20")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    orders = PortfolioRepository(db_session).list_orders()

    assert response.action == "bought"
    assert len(orders) == 1
    assert orders[0].quantity == profile.order_quantity


def test_moving_average_cross_manual_run_buys_from_persisted_strategy_candles(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    symbol = "ETHUSDT"
    timeframe = "5m"
    candle_source = "binance"
    strategy, bot, _ = bot_stack_factory(db_session, symbol=symbol)
    reset_draft_balance(db_session, bot.id)
    configure_moving_average_strategy(strategy)
    strategy.timeframe = timeframe
    strategy.parameters["candle_source"] = candle_source
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, symbol=symbol, timeframe=timeframe, closes=["30", "30", "30", "10"], source="manual")
    add_candles(db_session, symbol=symbol, timeframe="1m", closes=["30", "30", "30", "10"], source=candle_source)
    add_candles(db_session, symbol="BTCUSDT", timeframe=timeframe, closes=["30", "30", "30", "10"], source=candle_source)
    add_candles(db_session, symbol=symbol, timeframe=timeframe, closes=["10", "10", "10", "20"], source=candle_source)

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price(symbol, "20")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "bought"
    assert response.message == "buy_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.previous_long_ma == Decimal("10.00000000")
    assert response.decision_explanation.current_long_ma == Decimal("13.33333333")
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].symbol == symbol
    assert orders[0].side == "buy"
    buy_signal = next(event for event in events if event.message == "buy_signal")
    assert buy_signal.payload["symbol"] == symbol
    assert buy_signal.payload["timeframe"] == timeframe
    assert buy_signal.payload["candle_source"] == candle_source
    assert buy_signal.payload["current_price"] == "20.00000000"


def test_moving_average_cross_manual_run_sells_from_persisted_strategy_candles(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    symbol = "ETHUSDT"
    timeframe = "5m"
    candle_source = "binance"
    strategy, bot, _ = bot_stack_factory(db_session, symbol=symbol)
    reset_draft_balance_with_base(db_session, bot.id, "ETH", Decimal("0.1"))
    configure_moving_average_strategy(strategy)
    strategy.timeframe = timeframe
    strategy.parameters["candle_source"] = candle_source
    db_session.add(strategy)
    seed_open_position(
        db_session,
        bot_id=bot.id,
        symbol=symbol,
        base_asset="ETH",
        quote_asset="USDT",
        quantity=Decimal("0.1"),
        average_entry_price=Decimal("20"),
    )
    db_session.commit()
    add_candles(db_session, symbol=symbol, timeframe=timeframe, closes=["10", "10", "10", "20"], source="manual")
    add_candles(db_session, symbol=symbol, timeframe="1m", closes=["10", "10", "10", "20"], source=candle_source)
    add_candles(db_session, symbol="BTCUSDT", timeframe=timeframe, closes=["10", "10", "10", "20"], source=candle_source)
    add_candles(db_session, symbol=symbol, timeframe=timeframe, closes=["20", "20", "20", "10"], source=candle_source)

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price(symbol, "10")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "sold"
    assert response.message == "sell_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.previous_long_ma == Decimal("20.00000000")
    assert response.decision_explanation.current_long_ma == Decimal("16.66666667")
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].symbol == symbol
    assert orders[0].side == "sell"
    assert orders[0].quantity == Decimal("0.10000000")
    sell_signal = next(event for event in events if event.message == "sell_signal")
    assert sell_signal.payload["symbol"] == symbol
    assert sell_signal.payload["timeframe"] == timeframe
    assert sell_signal.payload["candle_source"] == candle_source


def test_moving_average_cross_manual_run_no_crossover_records_skipped_event(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    symbol = "ETHUSDT"
    timeframe = "5m"
    candle_source = "binance"
    strategy, bot, _ = bot_stack_factory(db_session, symbol=symbol)
    reset_draft_balance(db_session, bot.id)
    configure_moving_average_strategy(strategy)
    strategy.timeframe = timeframe
    strategy.parameters["candle_source"] = candle_source
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, symbol=symbol, timeframe=timeframe, closes=["10", "10", "10", "20"], source="manual")
    add_candles(db_session, symbol=symbol, timeframe=timeframe, closes=["10", "11", "12", "13"], source=candle_source)

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price(symbol, "13")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.reason == "moving averages did not cross bullish, so no buy signal"
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["symbol"] == symbol
    assert skipped_event.payload["timeframe"] == timeframe
    assert skipped_event.payload["candle_source"] == candle_source
    assert skipped_event.payload["current_short_ma"] == "12.50000000"
    assert skipped_event.payload["decision"] == "skipped"


def test_moving_average_cross_manual_run_insufficient_persisted_candles_records_skipped_event(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    symbol = "ETHUSDT"
    timeframe = "5m"
    candle_source = "binance"
    strategy, bot, _ = bot_stack_factory(db_session, symbol=symbol)
    reset_draft_balance(db_session, bot.id)
    configure_moving_average_strategy(strategy)
    strategy.timeframe = timeframe
    strategy.parameters["candle_source"] = candle_source
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, symbol=symbol, timeframe=timeframe, closes=["10", "10", "10", "20"], source="manual")
    add_candles(db_session, symbol=symbol, timeframe=timeframe, closes=["10", "10", "20"], source=candle_source)

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price(symbol, "20")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.reason == "insufficient_candles"
    assert response.decision_explanation.candles_used == 3
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["symbol"] == symbol
    assert skipped_event.payload["timeframe"] == timeframe
    assert skipped_event.payload["candle_source"] == candle_source
    assert skipped_event.payload["candles_used"] == 3


def test_moving_average_cross_sell_crossover_sells_existing_position(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_with_base(db_session, bot.id, "BTC", Decimal("0.1"))
    configure_moving_average_strategy(strategy)
    db_session.add(strategy)
    seed_open_position(
        db_session,
        bot_id=bot.id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=Decimal("0.1"),
        average_entry_price=Decimal("20"),
    )
    db_session.commit()
    add_candles(db_session, closes=["20", "20", "20", "10"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "10")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)

    assert response.action == "sold"
    assert response.message == "sell_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "sell"
    assert response.decision_explanation.reason == "short moving average crossed below long moving average"
    assert response.decision_explanation.previous_short_ma == Decimal("20.00000000")
    assert response.decision_explanation.current_short_ma == Decimal("15.00000000")
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].side == "sell"
    assert orders[0].quantity == Decimal("0.10000000")
    assert repository.get_position_by_symbol("BTCUSDT").quantity == Decimal("0E-8")


def test_moving_average_cross_no_crossover_skips_safely(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_moving_average_strategy(strategy)
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "11", "12", "13"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "13")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "moving averages did not cross bullish, so no buy signal"
    assert response.decision_explanation.previous_short_ma == Decimal("11.50000000")
    assert response.decision_explanation.current_short_ma == Decimal("12.50000000")
    assert PortfolioRepository(db_session).list_orders() == []


def test_moving_average_cross_insufficient_candles_skips_safely(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_moving_average_strategy(strategy)
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "10", "20"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "20")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "insufficient_candles"
    assert response.decision_explanation.candles_used == 3
    assert PortfolioRepository(db_session).list_orders() == []


def test_moving_average_cross_invalid_parameters_skip_safely(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_moving_average_strategy(strategy, short_window="2.5")
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "10", "10", "20"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "20")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "strategy parameter short_window must be a positive integer"
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["parameter"] == "short_window"


def test_macd_crossover_buy_crossover_creates_buy_paper_order(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_macd_crossover_strategy(strategy)
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["1", "1", "1", "1", "2"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "2")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "bought"
    assert response.message == "buy_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "buy"
    assert response.decision_explanation.reason == "macd crossed above signal line"
    assert response.decision_explanation.candles_used == 5
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].quantity == Decimal("0.10000000")
    assert repository.get_position_by_symbol("BTCUSDT") is not None

    buy_signal = next(event for event in events if event.message == "buy_signal")
    assert buy_signal.payload["strategy_type"] == "macd_crossover"
    assert buy_signal.payload["fast_period"] == 2
    assert buy_signal.payload["slow_period"] == 3
    assert buy_signal.payload["signal_period"] == 2
    assert buy_signal.payload["macd"] == "0.16666667"
    assert buy_signal.payload["signal"] == "0.11111111"
    assert buy_signal.payload["histogram"] == "0.05555556"


def test_macd_crossover_uses_configured_candle_source(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_macd_crossover_strategy(strategy)
    strategy.parameters["candle_source"] = "binance"
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["1", "1", "1", "1", "1"], source="manual")
    add_candles(db_session, closes=["1", "1", "1", "1", "2"], source="binance")

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "2")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "bought"
    buy_signal = next(event for event in events if event.message == "buy_signal")
    assert buy_signal.payload["strategy_type"] == "macd_crossover"
    assert buy_signal.payload["candle_source"] == "binance"
    assert buy_signal.payload["macd"] == "0.16666667"
    assert buy_signal.payload["signal"] == "0.11111111"


def test_macd_crossover_sell_crossover_sells_existing_position(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_with_base(db_session, bot.id, "BTC", Decimal("0.1"))
    configure_macd_crossover_strategy(strategy)
    db_session.add(strategy)
    seed_open_position(
        db_session,
        bot_id=bot.id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=Decimal("0.1"),
        average_entry_price=Decimal("2"),
    )
    db_session.commit()
    add_candles(db_session, closes=["1", "1", "1", "2", "1"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "1")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "sold"
    assert response.message == "sell_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "sell"
    assert response.decision_explanation.reason == "macd crossed below signal line"
    assert response.decision_explanation.candles_used == 5
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].side == "sell"
    assert orders[0].quantity == Decimal("0.10000000")
    assert repository.get_position_by_symbol("BTCUSDT").quantity == Decimal("0E-8")

    sell_signal = next(event for event in events if event.message == "sell_signal")
    assert sell_signal.payload["strategy_type"] == "macd_crossover"
    assert sell_signal.payload["macd"] == "-0.02777778"
    assert sell_signal.payload["signal"] == "0.00925926"
    assert sell_signal.payload["histogram"] == "-0.03703704"


def test_macd_crossover_insufficient_candles_skips_safely(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_macd_crossover_strategy(strategy)
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["1", "1", "2", "3"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "3")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "insufficient_candles"
    assert response.decision_explanation.candles_used == 4
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["strategy_type"] == "macd_crossover"
    assert skipped_event.payload["candles_used"] == 4


def test_macd_crossover_invalid_parameters_skip_safely(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_macd_crossover_strategy(strategy, fast_period="2.5")
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["1", "1", "1", "1", "2"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "2")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "strategy parameter fast_period must be a positive integer"
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["strategy_type"] == "macd_crossover"
    assert skipped_event.payload["parameter"] == "fast_period"


def test_macd_crossover_missing_quantity_uses_execution_profile_quantity(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, profile = bot_stack_factory(db_session)
    assert profile is not None
    reset_draft_balance(db_session, bot.id)
    configure_macd_crossover_strategy(strategy)
    strategy.parameters.pop("quantity")
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["1", "1", "1", "1", "2"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "2")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    orders = PortfolioRepository(db_session).list_orders()

    assert response.action == "bought"
    assert len(orders) == 1
    assert orders[0].quantity == profile.order_quantity


def test_rsi_threshold_buy_signal_creates_buy_paper_order(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_rsi_threshold_strategy(strategy)
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["12", "11", "10"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "10")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "bought"
    assert response.message == "buy_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "buy"
    assert response.decision_explanation.reason == "rsi is at or below oversold threshold"
    assert response.decision_explanation.candles_used == 3
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].quantity == Decimal("0.10000000")
    assert repository.get_position_by_symbol("BTCUSDT") is not None

    buy_signal = next(event for event in events if event.message == "buy_signal")
    assert buy_signal.payload["strategy_type"] == "rsi_threshold"
    assert buy_signal.payload["period"] == 2
    assert buy_signal.payload["oversold"] == "30"
    assert buy_signal.payload["overbought"] == "70"
    assert buy_signal.payload["rsi"] == "0.00000000"


def test_rsi_threshold_sell_signal_sells_existing_position(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_with_base(db_session, bot.id, "BTC", Decimal("0.1"))
    configure_rsi_threshold_strategy(strategy)
    db_session.add(strategy)
    seed_open_position(
        db_session,
        bot_id=bot.id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=Decimal("0.1"),
        average_entry_price=Decimal("10"),
    )
    db_session.commit()
    add_candles(db_session, closes=["10", "11", "12"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "12")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "sold"
    assert response.message == "sell_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "sell"
    assert response.decision_explanation.reason == "rsi is at or above overbought threshold"
    assert response.decision_explanation.candles_used == 3
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].side == "sell"
    assert orders[0].quantity == Decimal("0.10000000")
    assert repository.get_position_by_symbol("BTCUSDT").quantity == Decimal("0E-8")

    sell_signal = next(event for event in events if event.message == "sell_signal")
    assert sell_signal.payload["strategy_type"] == "rsi_threshold"
    assert sell_signal.payload["rsi"] == "100.00000000"


def test_rsi_threshold_insufficient_candles_skips_safely(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_rsi_threshold_strategy(strategy)
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["12", "11"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "11")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "insufficient_candles"
    assert response.decision_explanation.candles_used == 2
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["strategy_type"] == "rsi_threshold"
    assert skipped_event.payload["candles_used"] == 2


def test_rsi_threshold_invalid_parameters_skip_safely(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_rsi_threshold_strategy(strategy, oversold="70", overbought="70")
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["12", "11", "10"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "10")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "rsi_threshold oversold must be less than overbought"
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["strategy_type"] == "rsi_threshold"
    assert skipped_event.payload["parameter"] == "oversold"


def test_rsi_threshold_missing_quantity_uses_execution_profile_quantity(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, profile = bot_stack_factory(db_session)
    assert profile is not None
    reset_draft_balance(db_session, bot.id)
    configure_rsi_threshold_strategy(strategy)
    strategy.parameters.pop("quantity")
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["12", "11", "10"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "10")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    orders = PortfolioRepository(db_session).list_orders()

    assert response.action == "bought"
    assert len(orders) == 1
    assert orders[0].quantity == profile.order_quantity


def test_bollinger_bands_buy_signal_creates_buy_paper_order(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_bollinger_bands_strategy(strategy)
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "10", "1"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "1")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "bought"
    assert response.message == "buy_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "buy"
    assert response.decision_explanation.reason == "price is at or below lower bollinger band"
    assert response.decision_explanation.candles_used == 3
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].quantity == Decimal("0.10000000")
    assert repository.get_position_by_symbol("BTCUSDT") is not None

    buy_signal = next(event for event in events if event.message == "buy_signal")
    assert buy_signal.payload["strategy_type"] == "bollinger_bands"
    assert buy_signal.payload["period"] == 3
    assert buy_signal.payload["stddev_multiplier"] == "0.5"
    assert buy_signal.payload["sma"] == "7.00000000"
    assert buy_signal.payload["lower_band"] == "4.87867966"


def test_bollinger_bands_sell_signal_sells_existing_position(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_with_base(db_session, bot.id, "BTC", Decimal("0.1"))
    configure_bollinger_bands_strategy(strategy)
    db_session.add(strategy)
    seed_open_position(
        db_session,
        bot_id=bot.id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=Decimal("0.1"),
        average_entry_price=Decimal("1"),
    )
    db_session.commit()
    add_candles(db_session, closes=["1", "1", "10"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "10")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "sold"
    assert response.message == "sell_filled"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "sell"
    assert response.decision_explanation.reason == "price is at or above upper bollinger band"
    assert response.decision_explanation.candles_used == 3
    orders = repository.list_orders()
    assert len(orders) == 1
    assert orders[0].side == "sell"
    assert orders[0].quantity == Decimal("0.10000000")
    assert repository.get_position_by_symbol("BTCUSDT").quantity == Decimal("0E-8")

    sell_signal = next(event for event in events if event.message == "sell_signal")
    assert sell_signal.payload["strategy_type"] == "bollinger_bands"
    assert sell_signal.payload["sma"] == "4.00000000"
    assert sell_signal.payload["upper_band"] == "6.12132034"


def test_bollinger_bands_insufficient_candles_skips_safely(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_bollinger_bands_strategy(strategy)
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "10"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "10")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "insufficient_candles"
    assert response.decision_explanation.candles_used == 2
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["strategy_type"] == "bollinger_bands"
    assert skipped_event.payload["candles_used"] == 2


def test_bollinger_bands_invalid_parameters_skip_safely(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    configure_bollinger_bands_strategy(strategy, period="1")
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "10", "1"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "1")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "evaluation_skipped"
    assert response.decision_explanation is not None
    assert response.decision_explanation.decision == "skipped"
    assert response.decision_explanation.reason == "bollinger_bands parameter period must be at least 2"
    assert PortfolioRepository(db_session).list_orders() == []
    skipped_event = next(event for event in events if event.message == "evaluation_skipped")
    assert skipped_event.payload["strategy_type"] == "bollinger_bands"
    assert skipped_event.payload["parameter"] == "period"


def test_bollinger_bands_missing_quantity_uses_execution_profile_quantity(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    strategy, bot, profile = bot_stack_factory(db_session)
    assert profile is not None
    reset_draft_balance(db_session, bot.id)
    configure_bollinger_bands_strategy(strategy)
    strategy.parameters.pop("quantity")
    db_session.add(strategy)
    db_session.commit()
    add_candles(db_session, closes=["10", "10", "1"])

    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "1")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    orders = PortfolioRepository(db_session).list_orders()

    assert response.action == "bought"
    assert len(orders) == 1
    assert orders[0].quantity == profile.order_quantity


def test_live_mode_bot_does_not_use_simulated_execution_for_buy_or_sell(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, is_paper=False)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)

    stub_market_data_service.set_price("BTCUSDT", "95")
    buy_response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    stub_market_data_service.set_price("BTCUSDT", "115")
    sell_response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    repository = PortfolioRepository(db_session)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert buy_response.action == "skipped"
    assert buy_response.message == "live_mode_not_implemented"
    assert sell_response.action == "no_action"
    assert sell_response.message == "evaluation_no_signal"
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_position_by_symbol("BTCUSDT") is None
    assert any(event.message == "buy_signal" for event in events)
    assert any(event.message == "live_mode_not_implemented" for event in events)
    assert not any(event.message == "order_filled" for event in events)


def test_inactive_strategy_is_skipped_without_placing_orders(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, strategy_is_active=False)
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert response.action == "skipped"
    assert response.message == "strategy_inactive"
    assert PortfolioRepository(db_session).list_orders() == []
    assert any(event.message == "strategy_inactive" for event in events)
    assert not any(event.message == "order_filled" for event in events)


def test_background_bot_does_not_rebuy_or_record_cooldown_noise(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    clock = FakeClock()
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, cooldown_seconds=60)
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service, clock=clock)
    runner.start_bot(bot.id)

    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    asyncio.run(runner.run_cycle())
    asyncio.run(runner.run_cycle())

    repository = PortfolioRepository(db_session)
    orders = repository.list_orders()
    events = RunEventRepository(db_session).list_for_bot(bot.id)
    status = runner.get_bot_status(bot.id)

    assert len(orders) == 2
    assert orders[0].side == "sell"
    assert orders[1].side == "buy"
    assert [event.message for event in events].count("cooldown_active") == 0
    assert status.cooldown_active is True
    assert status.current_position_quantity == Decimal("0E-8")


def test_bot_can_buy_again_after_cooldown_expires(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    clock = FakeClock()
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, cooldown_seconds=60)
    reset_draft_balance(db_session, bot.id)
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


def test_status_reflects_current_state(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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


def test_pause_endpoint_marks_bot_as_paused(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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


def test_resume_endpoint_marks_bot_as_active_again(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    asyncio.run(pause_bot_endpoint(bot.id, runner))
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())
    asyncio.run(runner.run_cycle())
    asyncio.run(runner.run_cycle())

    repository = PortfolioRepository(db_session)
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert attempts == []
    assert any(event.message == "bot_paused" for event in events)
    assert [event.message for event in events].count("bot_skipped_paused") == 0


def test_background_no_signal_evaluations_do_not_create_repeated_activity(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "105")

    asyncio.run(runner.run_cycle())
    asyncio.run(runner.run_cycle())
    asyncio.run(runner.run_cycle())

    events = RunEventRepository(db_session).list_for_bot(bot.id)

    assert [event.message for event in events].count("evaluation_no_signal") == 0
    assert PortfolioRepository(db_session).list_orders() == []


def test_background_meaningful_events_are_still_recorded(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    events = RunEventRepository(db_session).list_for_bot(bot.id)
    messages = [event.message for event in events]

    assert "buy_signal" in messages
    assert "order_filled" in messages
    assert PortfolioRepository(db_session).list_orders()


def test_resumed_bot_can_trade_again(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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
    assert any(event.message == "bot_paused" for event in events)
    assert not any(event.message == "bot_skipped_paused" for event in events)
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
    bot_stack_factory,
) -> None:
    _, first_bot, _ = bot_stack_factory(db_session, name="BTC threshold bot", symbol="BTCUSDT")
    _, second_bot, _ = bot_stack_factory(db_session, name="ETH threshold bot", symbol="ETHUSDT")
    reset_draft_balance(db_session, first_bot.id)
    reset_draft_balance(db_session, second_bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(list_bots_endpoint(runner))

    assert [item.bot_id for item in response.items] == [second_bot.id, first_bot.id]
    assert [item.name for item in response.items] == ["ETH threshold bot", "BTC threshold bot"]


def test_bots_dashboard_includes_paused_state(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, name="Paused bot", symbol="BTCUSDT", status="paused")
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
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, name="Cooldown bot", symbol="BTCUSDT", cooldown_seconds=60)
    reset_draft_balance(db_session, bot.id)
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
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, name="Position bot", symbol="BTCUSDT")
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())

    response = asyncio.run(list_bots_endpoint(runner))

    assert response.items[0].current_position_qty == Decimal("0.10000000")
    assert response.items[0].last_price == Decimal("95")


def test_selected_bot_read_models_ignore_global_and_other_bot_positions(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    strategy, selected_bot, _ = bot_stack_factory(
        db_session,
        name="Selected position bot",
        symbol="BTCUSDT",
        status="active",
    )
    _, other_bot, _ = bot_stack_factory(
        db_session,
        name="Other position bot",
        symbol="BTCUSDT",
        status="active",
    )
    db_session.add(
        Position(
            symbol=strategy.symbol,
            quantity=Decimal("0.5"),
            average_entry_price=Decimal("90"),
            realized_pnl=Decimal("7.25"),
        )
    )
    db_session.add(
        PaperPosition(
            bot_id=other_bot.id,
            symbol=strategy.symbol,
            base_asset="BTC",
            quote_asset="USDT",
            quantity=Decimal("0.25"),
            average_entry_price=Decimal("80"),
            realized_pnl=Decimal("3.50"),
        )
    )
    db_session.commit()
    stub_market_data_service.set_price(strategy.symbol, "100")
    runner = build_runner(db_session_factory, stub_market_data_service)

    dashboard = asyncio.run(list_bots_endpoint(runner))
    summary = asyncio.run(get_bot_summary_endpoint(selected_bot.id, runner))
    status = runner.get_bot_status(selected_bot.id)

    selected_dashboard_item = next(item for item in dashboard.items if item.bot_id == selected_bot.id)
    assert selected_dashboard_item.current_position_qty == Decimal("0")
    assert summary.current_position_qty == Decimal("0")
    assert status.current_position_quantity == Decimal("0")


def test_paper_decision_ignores_legacy_global_position_when_bot_scoped_position_missing(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    # Regression: paper-mode decisions must use bot-scoped paper positions, not
    # legacy/global same-symbol positions owned by another bot or old state.
    funded_account(db_session)
    strategy_a, bot_a, _ = bot_stack_factory(
        db_session,
        name="Scoped position bot",
        symbol="BTCUSDT",
        status="active",
    )
    _, bot_b, _ = bot_stack_factory(
        db_session,
        name="Legacy decision bot",
        symbol="BTCUSDT",
        status="active",
    )
    reset_draft_balance(db_session, bot_b.id)
    db_session.add(
        Position(
            symbol=strategy_a.symbol,
            quantity=Decimal("0.5"),
            average_entry_price=Decimal("90"),
            realized_pnl=Decimal("7.25"),
        )
    )
    db_session.add(
        PaperPosition(
            bot_id=bot_a.id,
            symbol=strategy_a.symbol,
            base_asset="BTC",
            quote_asset="USDT",
            quantity=Decimal("0.25"),
            average_entry_price=Decimal("80"),
            realized_pnl=Decimal("3.50"),
        )
    )
    db_session.commit()
    stub_market_data_service.set_price(strategy_a.symbol, "115")
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(run_bot_once_endpoint(bot_b.id, runner))
    dashboard = asyncio.run(list_bots_endpoint(runner))
    summary = asyncio.run(get_bot_summary_endpoint(bot_b.id, runner))
    status = runner.get_bot_status(bot_b.id)
    run_events = asyncio.run(
        list_run_events_endpoint(
            db_session,
            bot_id=bot_b.id,
            run_id=None,
            event_type=None,
            level=None,
        )
    )

    assert response.action == "no_action"
    assert response.message == "evaluation_no_signal"
    assert response.current_position_qty == Decimal("0")
    assert response.decision_explanation is not None
    assert response.decision_explanation.position_qty == Decimal("0")
    assert response.decision_explanation.decision == "hold"
    assert response.decision_explanation.reason == "price did not go below buy_below, so no buy signal"

    messages = [event.message for event in run_events]
    assert "sell_signal" not in messages
    assert "order_rejected" not in messages
    assert PortfolioRepository(db_session).list_orders() == []

    selected_dashboard_item = next(item for item in dashboard.items if item.bot_id == bot_b.id)
    assert selected_dashboard_item.current_position_qty == Decimal("0")
    assert summary.current_position_qty == Decimal("0")
    assert status.current_position_quantity == Decimal("0")


def test_paper_sell_settles_from_bot_scoped_state_when_legacy_global_position_missing(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    # Regression: bot-scoped draft balance and paper position are the source of
    # truth for paper sells; legacy/global position state is only a compatibility mirror.
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(
        db_session,
        name="Scoped sell without legacy position bot",
        symbol="BTCUSDT",
        status="active",
    )
    reset_draft_balance_with_base(db_session, bot.id, "BTC", Decimal("0.1"))
    db_session.add(
        PaperPosition(
            bot_id=bot.id,
            symbol=strategy.symbol,
            base_asset="BTC",
            quote_asset="USDT",
            quantity=Decimal("0.1"),
            average_entry_price=Decimal("95"),
            realized_pnl=Decimal("0"),
        )
    )
    db_session.commit()
    stub_market_data_service.set_price(strategy.symbol, "115")
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    run_events = asyncio.run(
        list_run_events_endpoint(
            db_session,
            bot_id=bot.id,
            run_id=None,
            event_type=None,
            level=None,
        )
    )
    orders = PortfolioRepository(db_session).list_orders()
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    persisted_paper_position = db_session.scalar(
        select(PaperPosition).where(
            PaperPosition.bot_id == bot.id,
            PaperPosition.symbol == strategy.symbol,
        )
    )
    btc_balance = DraftBalanceRepository(db_session).get_for_bot_asset(bot_id=bot.id, asset="BTC")
    usdt_balance = DraftBalanceRepository(db_session).get_for_bot_asset(bot_id=bot.id, asset="USDT")
    snapshots = PaperEquitySnapshotRepository(db_session).list_latest_for_bot(bot_id=bot.id)

    assert response.action == "sold"
    assert response.message == "sell_filled"
    assert response.current_position_qty == Decimal("0E-8")
    assert response.decision_explanation is not None
    assert response.decision_explanation.position_qty == Decimal("0.1")
    assert response.decision_explanation.decision == "sell"
    assert response.decision_explanation.reason == "price is above strategy sell_above and position exists"

    sell_signal = next(event for event in run_events if event.message == "sell_signal")
    filled = next(event for event in run_events if event.message == "order_filled")
    assert sell_signal.payload["quantity"] == "0.10000000"
    assert filled.payload["message"] == "Market sell order filled"
    assert orders[0].status == "filled"
    assert orders[0].rejection_reason is None
    assert attempts[0].final_status == "filled"
    assert attempts[0].final_reason == "Market sell order filled"
    assert PortfolioRepository(db_session).get_position_by_symbol(strategy.symbol) is None
    assert persisted_paper_position is not None
    assert persisted_paper_position.quantity == Decimal("0E-8")
    assert persisted_paper_position.realized_pnl == Decimal("2.00000000")
    assert btc_balance is not None
    assert btc_balance.available == Decimal("0E-8")
    assert btc_balance.locked == Decimal("0")
    assert usdt_balance is not None
    assert usdt_balance.available == Decimal("10011.50000000")
    assert usdt_balance.locked == Decimal("0E-8")
    assert len(snapshots) == 1
    assert snapshots[0].event_type == "sell_fill"
    assert snapshots[0].source_order_id == orders[0].id
    assert snapshots[0].source_fill_id == filled.payload["fill_id"]


def test_bots_dashboard_response_shape_stays_minimal_and_clean(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    bot_stack_factory(db_session, name="Shape bot", symbol="BTCUSDT", status="paused")
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
    bot_stack_factory,
) -> None:
    strategy, bot, _ = bot_stack_factory(db_session, name="BTC threshold bot", symbol="BTCUSDT")
    reset_draft_balance(db_session, bot.id)
    strategy.parameters = {
        "buy_below": "100",
        "sell_above": "110",
        "quantity": "0.1",
    }
    db_session.add(strategy)
    db_session.commit()
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(get_bot_summary_endpoint(bot.id, runner))

    assert response.bot_id == bot.id
    assert response.name == "BTC threshold bot"
    assert response.status == "draft"
    assert response.is_paused is False
    assert response.strategy_type == "price_threshold"
    assert response.strategy_name == "BTC threshold bot Strategy"
    assert response.strategy_timeframe == "1m"
    assert response.strategy_parameters == {
        "buy_below": "100",
        "sell_above": "110",
        "quantity": "0.1",
    }
    assert response.symbol == "BTCUSDT"
    assert response.cooldown_seconds == 60
    assert response.buy_below_price == Decimal("100.00000000")
    assert response.sell_above_price == Decimal("110.00000000")
    assert response.recent_activity == []


def test_bot_summary_includes_paused_state_when_paused(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, name="Paused summary bot", symbol="BTCUSDT", status="paused")
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(get_bot_summary_endpoint(bot.id, runner))

    assert response.status == "paused"
    assert response.is_paused is True


def test_bot_summary_includes_cooldown_state_when_active(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, name="Cooldown summary bot", symbol="BTCUSDT", cooldown_seconds=60)
    reset_draft_balance(db_session, bot.id)
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
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, name="Position summary bot", symbol="BTCUSDT")
    reset_draft_balance(db_session, bot.id)
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
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, name="Activity summary bot", symbol="BTCUSDT")
    reset_draft_balance(db_session, bot.id)
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
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, name="Capped summary bot", symbol="BTCUSDT", cooldown_seconds=0)
    reset_draft_balance(db_session, bot.id)
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


def test_manual_bot_run_draft_bot_records_recent_activity(
    db_session,
    db_session_factory,
    stub_market_data_service,
    draft_bot,
) -> None:
    bot = draft_bot
    runner = build_runner(db_session_factory, stub_market_data_service)

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    run_events = asyncio.run(
        list_run_events_endpoint(
            db_session,
            bot_id=bot.id,
            run_id=None,
            event_type=None,
            level=None,
        )
    )

    assert response.action == "skipped"
    assert response.message == "bot_not_active"
    assert response.status == "draft"
    assert response.recent_activity_preview[0].message == "bot_not_active"
    assert [event.message for event in run_events] == ["bot_not_active"]


def test_manual_bot_run_paused_bot_returns_skipped_result(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, mode="paper") == []
    assert PaperEquitySnapshotRepository(db_session).list_latest_for_bot(bot_id=bot.id) == []


def test_manual_bot_run_missing_execution_profile_creates_expected_event(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, create_execution_profile=False)
    runner = build_runner(db_session_factory, stub_market_data_service)
    bot.status = "active"
    db_session.add(bot)
    db_session.commit()
    db_session.refresh(bot)

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    run_events = asyncio.run(
        list_run_events_endpoint(
            db_session,
            bot_id=bot.id,
            run_id=None,
            event_type=None,
            level=None,
        )
    )

    assert response.action == "skipped"
    assert response.message == "execution_profile_missing"
    assert response.recent_activity_preview[0].message == "execution_profile_missing"
    assert [event.message for event in run_events] == ["execution_profile_missing"]


def test_manual_bot_run_disabled_execution_profile_creates_expected_event(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, execution_profile_enabled=False)
    runner = build_runner(db_session_factory, stub_market_data_service)
    bot.status = "active"
    db_session.add(bot)
    db_session.commit()
    db_session.refresh(bot)

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    run_events = asyncio.run(
        list_run_events_endpoint(
            db_session,
            bot_id=bot.id,
            run_id=None,
            event_type=None,
            level=None,
        )
    )

    assert response.action == "skipped"
    assert response.message == "execution_profile_disabled"
    assert response.recent_activity_preview[0].message == "execution_profile_disabled"
    assert [event.message for event in run_events] == ["execution_profile_disabled"]


def test_manual_bot_run_cooldown_active_returns_skipped_result(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, cooldown_seconds=60)
    reset_draft_balance(db_session, bot.id)
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
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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
    assert response.decision_explanation is not None
    assert response.decision_explanation.current_price == Decimal("95")
    assert response.decision_explanation.buy_below == Decimal("100")
    assert response.decision_explanation.sell_above == Decimal("110")
    assert response.decision_explanation.position_qty == Decimal("0")
    assert response.decision_explanation.decision == "buy"
    assert response.decision_explanation.reason == "price is below strategy buy_below"
    assert response.recent_activity_preview[0].message == "buy_filled"
    assert len(PortfolioRepository(db_session).list_orders_filtered(bot_id=bot.id, mode="paper")) == 1
    assert len(PortfolioRepository(db_session).list_fills()) == 1
    assert len(ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, mode="paper")) == 1
    assert len(PaperEquitySnapshotRepository(db_session).list_latest_for_bot(bot_id=bot.id)) == 1


def test_duplicate_manual_buy_run_does_not_double_create_bot_scoped_artifacts(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    first_response = asyncio.run(run_bot_once_endpoint(bot.id, runner))
    duplicate_response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    repository = PortfolioRepository(db_session)
    orders = repository.list_orders_filtered(bot_id=bot.id, mode="paper")
    fills = repository.list_fills()
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, mode="paper")
    snapshots = PaperEquitySnapshotRepository(db_session).list_latest_for_bot(bot_id=bot.id)
    position = runner.get_bot_status(bot.id)
    draft_assets = {
        row.asset: row for row in DraftBalanceRepository(db_session).list_for_bot(bot.id)
    }

    assert first_response.action == "bought"
    assert first_response.message == "buy_filled"
    assert duplicate_response.action == "no_action"
    assert duplicate_response.message == "evaluation_no_signal"
    assert duplicate_response.decision_explanation is not None
    assert duplicate_response.decision_explanation.position_qty == Decimal("0.10000000")
    assert duplicate_response.decision_explanation.decision == "hold"
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].status == "filled"
    assert len(fills) == 1
    assert len(attempts) == 1
    assert attempts[0].final_status == "filled"
    assert len(snapshots) == 1
    assert snapshots[0].event_type == "buy_fill"
    assert draft_assets["USDT"].available == Decimal("9990.50000000")
    assert draft_assets["USDT"].locked == Decimal("0E-8")
    assert draft_assets["BTC"].available == Decimal("0.10000000")
    assert draft_assets["BTC"].locked == Decimal("0E-8")
    assert position.current_position_quantity == Decimal("0.10000000")


def test_manual_bot_run_sell_eligible_returns_sold_result(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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
    assert response.decision_explanation is not None
    assert response.decision_explanation.current_price == Decimal("115")
    assert response.decision_explanation.buy_below == Decimal("100")
    assert response.decision_explanation.sell_above == Decimal("110")
    assert response.decision_explanation.position_qty == Decimal("0.10000000")
    orders = PortfolioRepository(db_session).list_orders_filtered(bot_id=bot.id, mode="paper")
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, mode="paper")
    snapshots = PaperEquitySnapshotRepository(db_session).list_latest_for_bot(bot_id=bot.id)
    draft_assets = {row.asset: row for row in DraftBalanceRepository(db_session).list_for_bot(bot.id)}
    assert len(orders) == 2
    assert [order.side for order in orders] == ["sell", "buy"]
    assert all(order.status == "filled" for order in orders)
    assert len(PortfolioRepository(db_session).list_fills()) == 2
    assert len(attempts) == 2
    assert [attempt.side for attempt in attempts] == ["sell", "buy"]
    assert all(attempt.final_status == "filled" for attempt in attempts)
    assert [snapshot.event_type for snapshot in snapshots] == ["sell_fill", "buy_fill"]
    assert draft_assets["BTC"].available == Decimal("0E-8")
    assert draft_assets["BTC"].locked == Decimal("0E-8")
    assert draft_assets["USDT"].locked == Decimal("0E-8")
    assert response.decision_explanation.decision == "sell"
    assert response.decision_explanation.reason == "price is above strategy sell_above and position exists"
    assert response.recent_activity_preview[0].message == "sell_filled"


def test_manual_bot_run_no_signal_returns_no_action(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "105")

    response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    assert response.action == "no_action"
    assert response.message == "evaluation_no_signal"
    assert response.cooldown_active is False
    assert response.current_position_qty == Decimal("0")
    assert response.decision_explanation is not None
    assert response.decision_explanation.current_price == Decimal("105")
    assert response.decision_explanation.buy_below == Decimal("100")
    assert response.decision_explanation.sell_above == Decimal("110")
    assert response.decision_explanation.position_qty == Decimal("0")
    assert response.decision_explanation.decision == "hold"
    assert response.decision_explanation.reason == "price did not go below buy_below, so no buy signal"
    assert response.recent_activity_preview[0].message == "evaluation_no_signal"


def test_manual_bot_run_response_includes_consistent_bot_state_fields(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
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
        "decision_explanation",
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
            object(),
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
            object(),
        )
    )

    response = asyncio.run(
        set_market_price_endpoint(
            MarketPriceUpdateRequest(symbol="btcusdt", price=Decimal("115.00000000")),
            stub_market_data_service,
            object(),
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
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot.id)
    runner = build_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)

    asyncio.run(
        set_market_price_endpoint(
            MarketPriceUpdateRequest(symbol="btcusdt", price=Decimal("95.00000000")),
            stub_market_data_service,
            runner,
        )
    )
    buy_response = asyncio.run(run_bot_once_endpoint(bot.id, runner))

    asyncio.run(
        set_market_price_endpoint(
            MarketPriceUpdateRequest(symbol="BTCUSDT", price=Decimal("115.00000000")),
            stub_market_data_service,
            runner,
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
            object(),
        )
    )

    assert set(response.model_dump()) == {"symbol", "price", "updated_at"}
