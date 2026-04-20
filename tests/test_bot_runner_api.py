import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient

from app.engine.bot_runner import BotRunner, RunnerConfig
from app.main import app
from app.models.bot import Bot
from app.models.execution_profile import ExecutionProfile
from app.models.strategy import Strategy


def create_bot_stack(session) -> int:
    strategy = Strategy(
        name="Threshold Strategy",
        description="API test strategy",
        symbol="BTCUSDT",
        timeframe="1m",
        is_active=True,
    )
    session.add(strategy)
    session.commit()
    session.refresh(strategy)

    bot = Bot(
        name="API Bot",
        strategy_id=strategy.id,
        exchange_name="binance",
        status="draft",
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
        default_order_type="market",
        is_enabled=True,
    )
    session.add(profile)
    session.commit()
    return bot.id


def test_bot_runtime_api_flow(db_session_factory, stub_market_data_service) -> None:
    with db_session_factory() as session:
        bot_id = create_bot_stack(session)

    app.state.db_session_factory = db_session_factory
    app.state.market_data_service = stub_market_data_service
    app.state.bot_runner = BotRunner(
        session_factory=db_session_factory,
        market_data_service=stub_market_data_service,
        config=RunnerConfig(
            enabled=True,
            poll_interval_seconds=3600,
            simulation_enabled=True,
            simulation_fee_bps=Decimal("0"),
            simulation_slippage_bps=Decimal("0"),
        ),
    )

    with TestClient(app) as client:
        start_response = client.post(f"/api/v1/bots/{bot_id}/start")
        initial_status_response = client.get(f"/api/v1/bots/{bot_id}/status")

        stub_market_data_service.set_price("BTCUSDT", "95")
        asyncio.run(app.state.bot_runner.run_cycle())
        stub_market_data_service.set_price("BTCUSDT", "115")
        asyncio.run(app.state.bot_runner.run_cycle())

        status_response = client.get(f"/api/v1/bots/{bot_id}/status")
        bot_runs_response = client.get("/api/v1/bot-runs", params={"bot_id": bot_id})
        run_events_response = client.get("/api/v1/run-events", params={"bot_id": bot_id})
        stop_response = client.post(f"/api/v1/bots/{bot_id}/stop")

    assert start_response.status_code == 200
    assert start_response.json()["bot_status"] == "active"
    assert start_response.json()["active_run_status"] == "running"

    assert initial_status_response.status_code == 200
    assert initial_status_response.json()["bot_id"] == bot_id
    assert initial_status_response.json()["runner_enabled"] is True
    assert initial_status_response.json()["cooldown_active"] is False

    assert status_response.status_code == 200
    assert status_response.json()["current_position_quantity"] == "0E-8"
    assert status_response.json()["last_event_message"] == "order_filled"

    assert bot_runs_response.status_code == 200
    assert len(bot_runs_response.json()) == 1
    assert bot_runs_response.json()[0]["status"] == "running"

    assert run_events_response.status_code == 200
    messages = [event["message"] for event in run_events_response.json()]
    assert "started" in messages
    assert "buy_signal" in messages
    assert "sell_signal" in messages
    assert messages.count("order_filled") == 2

    assert stop_response.status_code == 200
    assert stop_response.json()["bot_status"] == "paused"
    assert stop_response.json()["active_run_id"] is None
