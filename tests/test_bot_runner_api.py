import asyncio
import queue
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.bot_runtime import get_bot_activity
from app.core.errors import NotFoundError
from app.data.providers.base import BaseMarketDataProvider
from app.data.schemas import MarketEvent, MarketEventType
from app.main import app
from app.services.market_data_service import MarketDataService


class PassiveBotRunner:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


class BlockingMarketDataProvider(BaseMarketDataProvider):
    def __init__(self, symbol: str = "BTCUSDT"):
        super().__init__(symbol)
        self.events: queue.Queue[MarketEvent | None] = queue.Queue()

    @property
    def name(self) -> str:
        return "binance"

    async def stream_events(self) -> AsyncIterator[MarketEvent]:
        while True:
            event = await asyncio.to_thread(self.events.get)
            if event is None:
                return
            yield event

    def emit_price(self, price: str) -> None:
        self.events.put(
            MarketEvent(
                provider=self.name,
                symbol=self.symbol,
                event_type=MarketEventType.TICKER,
                event_ts=datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc),
                price=Decimal(price),
                close=Decimal(price),
            )
        )

    def close(self) -> None:
        self.events.put(None)


@pytest.fixture
def activity_bot_id(
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    bot_runner_factory,
    configure_app_state,
    funded_account,
    set_latest_market_price,
):
    with db_session_factory() as session:
        funded_account(session)
        _, bot, _ = bot_stack_factory(session, name="API Bot", description="API test strategy")
        bot_id = bot.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )
    app.state.bot_runner.start_bot(bot_id)

    async def run_cycles() -> None:
        set_latest_market_price("95")
        await app.state.bot_runner.run_cycle()
        set_latest_market_price("115")
        await app.state.bot_runner.run_cycle()
        set_latest_market_price("95")
        await app.state.bot_runner.run_cycle()

    asyncio.run(run_cycles())
    app.state.bot_runner = PassiveBotRunner()
    return bot_id


def test_bot_runtime_api_flow(
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    bot_runner_factory,
    configure_app_state,
    set_latest_market_price,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session, name="API Bot", description="API test strategy")
        bot_id = bot.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        start_response = client.post(f"/api/v1/bots/{bot_id}/start")
        initial_status_response = client.get(f"/api/v1/bots/{bot_id}/status")

        async def run_cycles() -> None:
            set_latest_market_price("95")
            await app.state.bot_runner.run_cycle()
            set_latest_market_price("115")
            await app.state.bot_runner.run_cycle()

        asyncio.run(run_cycles())

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


def test_manual_run_api_for_active_bot_returns_visible_recent_activity(
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    bot_runner_factory,
    configure_app_state,
    funded_account,
    set_latest_market_price,
) -> None:
    with db_session_factory() as session:
        funded_account(session)
        _, bot, _ = bot_stack_factory(session, name="Manual API Bot", description="Manual run API test strategy")
        bot_id = bot.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        start_response = client.post(f"/api/v1/bots/{bot_id}/start")
        set_latest_market_price("95")
        run_response = client.post(f"/api/v1/bots/{bot_id}/run")
        activity_response = client.get(f"/api/v1/bots/{bot_id}/activity", params={"limit": 3})

    assert start_response.status_code == 200

    assert run_response.status_code == 200
    assert run_response.json()["action"] == "bought"
    assert run_response.json()["message"] == "buy_filled"
    assert run_response.json()["recent_activity_preview"][0]["message"] == "buy_filled"
    assert run_response.json()["recent_activity_preview"][0]["type"] == "order_filled"

    assert activity_response.status_code == 200
    assert activity_response.json()["bot_id"] == bot_id
    assert activity_response.json()["items"][0]["message"] == "buy_filled"
    assert activity_response.json()["items"][0]["type"] == "order_filled"
    assert activity_response.json()["items"][0]["side"] == "buy"


def test_manual_market_price_update_syncs_bot_summary_and_run(
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    bot_runner_factory,
    configure_app_state,
    funded_account,
) -> None:
    with db_session_factory() as session:
        funded_account(session)
        _, bot, _ = bot_stack_factory(session, name="Manual Price API Bot")
        bot_id = bot.id

    runner_market_data_service = type(stub_market_data_service)()
    runner_market_data_service.set_price("BTCUSDT", "75638.95000000")
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(market_data_service=runner_market_data_service),
    )

    with TestClient(app) as client:
        start_response = client.post(f"/api/v1/bots/{bot_id}/start")
        price_response = client.post("/api/v1/market/price", json={"symbol": "btcusdt", "price": "95"})
        summary_response = client.get(f"/api/v1/bots/{bot_id}/summary")
        run_response = client.post(f"/api/v1/bots/{bot_id}/run")
        summary_after_run_response = client.get(f"/api/v1/bots/{bot_id}/summary")

    runner_latest = runner_market_data_service.get_latest("BTCUSDT")

    assert start_response.status_code == 200
    assert price_response.status_code == 200
    assert price_response.json()["symbol"] == "BTCUSDT"
    assert price_response.json()["price"] == "95"
    assert runner_latest is not None
    assert runner_latest.price == Decimal("95")

    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["name"] == "Manual Price API Bot"
    assert summary["symbol"] == "BTCUSDT"
    assert summary["strategy_type"] == "price_threshold"
    assert summary["cooldown_active"] is False
    assert summary["current_position_qty"] == "0"
    assert summary["last_price"] == "95"

    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["action"] == "bought"
    assert run_body["message"] == "buy_filled"
    assert run_body["last_price"] == "95"
    assert run_body["decision_explanation"]["current_price"] == "95"
    assert run_body["decision_explanation"]["decision"] == "buy"

    assert summary_after_run_response.status_code == 200
    summary_after_run = summary_after_run_response.json()
    assert summary_after_run["last_price"] == "95"
    assert summary_after_run["current_position_qty"] == "0.10000000"


def test_manual_market_price_survives_active_market_data_stream(
    db_session_factory,
    bot_stack_factory,
    bot_runner_factory,
    configure_app_state,
    funded_account,
) -> None:
    with db_session_factory() as session:
        funded_account(session)
        _, bot, _ = bot_stack_factory(session, name="Manual Stream API Bot")
        bot_id = bot.id

    provider = BlockingMarketDataProvider()
    market_data_service = MarketDataService(provider=provider, enabled=True)
    configure_app_state(
        market_data_service=market_data_service,
        bot_runner=bot_runner_factory(market_data_service=market_data_service),
    )

    with TestClient(app) as client:
        start_response = client.post(f"/api/v1/bots/{bot_id}/start")
        price_response = client.post("/api/v1/market/price", json={"symbol": "BTCUSDT", "price": "95"})
        provider.emit_price("75747.58")
        time.sleep(0.1)
        summary_response = client.get(f"/api/v1/bots/{bot_id}/summary")
        run_response = client.post(f"/api/v1/bots/{bot_id}/run")
        provider.close()

    assert start_response.status_code == 200
    assert price_response.status_code == 200
    assert summary_response.status_code == 200
    assert summary_response.json()["last_price"] == "95"
    assert run_response.status_code == 200
    assert run_response.json()["last_price"] == "95"
    assert run_response.json()["decision_explanation"]["current_price"] == "95"


def test_manual_run_api_for_draft_bot_returns_controlled_response_and_activity_event(
    draft_bot,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        run_response = client.post(f"/api/v1/bots/{draft_bot.id}/run")
        activity_response = client.get(f"/api/v1/bots/{draft_bot.id}/activity", params={"limit": 3})

    assert run_response.status_code == 200
    assert run_response.json()["status"] == "draft"
    assert run_response.json()["action"] == "skipped"
    assert run_response.json()["message"] == "bot_not_active"
    assert run_response.json()["recent_activity_preview"][0]["message"] == "bot_not_active"

    assert activity_response.status_code == 200
    assert activity_response.json()["items"][0]["message"] == "bot_not_active"
    assert activity_response.json()["items"][0]["type"] == "run_event"


def test_bot_activity_returns_recent_activity_for_a_bot(db_session_factory, activity_bot_id) -> None:
    bot_id = activity_bot_id

    with db_session_factory() as session:
        response = asyncio.run(get_bot_activity(bot_id, session, limit=20))

    assert response.bot_id == bot_id
    assert response.items
    assert response.items[0].message == "cooldown_active"
    assert any(item.message == "buy_filled" for item in response.items)
    assert any(item.message == "sell_filled" for item in response.items)


def test_bot_activity_newest_items_come_first(db_session_factory, activity_bot_id) -> None:
    bot_id = activity_bot_id

    with db_session_factory() as session:
        response = asyncio.run(get_bot_activity(bot_id, session, limit=20))

    messages = [item.message for item in response.items]
    assert messages[:4] == ["cooldown_active", "sell_filled", "sell_signal", "buy_filled"]


def test_bot_activity_includes_cooldown_active_when_present(db_session_factory, activity_bot_id) -> None:
    bot_id = activity_bot_id

    with db_session_factory() as session:
        response = asyncio.run(get_bot_activity(bot_id, session, limit=20))

    cooldown_items = [item for item in response.items if item.message == "cooldown_active"]
    assert len(cooldown_items) == 1
    assert cooldown_items[0].type == "run_event"
    assert cooldown_items[0].cooldown_until is not None


def test_bot_activity_respects_limit(db_session_factory, activity_bot_id) -> None:
    bot_id = activity_bot_id

    with db_session_factory() as session:
        response = asyncio.run(get_bot_activity(bot_id, session, limit=2))

    assert [item.message for item in response.items] == ["cooldown_active", "sell_filled"]


def test_bot_activity_api_returns_newest_items_first(activity_bot_id) -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{activity_bot_id}/activity", params={"limit": 4})

    assert response.status_code == 200
    assert [item["message"] for item in response.json()["items"]] == [
        "cooldown_active",
        "sell_filled",
        "sell_signal",
        "buy_filled",
    ]


def test_bot_activity_api_response_shape_contains_dashboard_fields(activity_bot_id) -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{activity_bot_id}/activity", params={"limit": 1})

    assert response.status_code == 200
    payload = response.json()

    assert set(payload) == {"bot_id", "items"}
    assert len(payload["items"]) == 1
    assert set(payload["items"][0]) == {
        "type",
        "timestamp",
        "message",
        "side",
        "price",
        "quantity",
        "cooldown_until",
    }


def test_bot_activity_returns_404_for_unknown_bot(
    db_session_factory,
    stub_market_data_service,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=PassiveBotRunner(),
    )

    with db_session_factory() as session:
        try:
            asyncio.run(get_bot_activity(999, session, limit=20))
        except NotFoundError as exc:
            assert exc.status_code == 404
            assert exc.error_code == "bot_not_found"
        else:
            raise AssertionError("Expected NotFoundError for unknown bot")
