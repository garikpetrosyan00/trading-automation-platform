from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.alert_event import AlertEvent
from app.models.alert_rule import AlertRule
from app.models.bot_run import BotRun
from app.models.execution_profile import ExecutionProfile
from app.models.run_event import RunEvent
from app.models.strategy import Strategy


def create_strategy(session, *, name: str = "API Strategy", symbol: str = "BTCUSDT") -> Strategy:
    strategy = Strategy(
        name=name,
        description="Bot API test strategy",
        symbol=symbol,
        timeframe="1m",
        is_active=True,
    )
    session.add(strategy)
    session.commit()
    session.refresh(strategy)
    return strategy


def test_create_bot_returns_created_bot_and_persists_it(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        strategy_id = create_strategy(session).id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    payload = {
        "name": "Momentum Bot",
        "strategy_id": strategy_id,
        "exchange_name": "binance",
        "status": "draft",
        "is_paper": True,
        "notes": "Created from API test",
    }

    with TestClient(app) as client:
        create_response = client.post("/api/v1/bots", json=payload)
        created_bot = create_response.json()
        get_response = client.get(f"/api/v1/bots/{created_bot['id']}")

    assert create_response.status_code == 201
    assert created_bot["name"] == payload["name"]
    assert created_bot["strategy_id"] == strategy_id
    assert created_bot["exchange_name"] == "binance"
    assert created_bot["status"] == "draft"
    assert created_bot["is_paper"] is True
    assert created_bot["notes"] == "Created from API test"
    assert set(created_bot) == {
        "id",
        "name",
        "strategy_id",
        "exchange_name",
        "status",
        "is_paper",
        "notes",
        "created_at",
        "updated_at",
    }

    assert get_response.status_code == 200
    assert get_response.json() == created_bot


def test_create_bot_with_invalid_payload_returns_validation_error(
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/bots",
            json={
                "name": "",
                "strategy_id": 1,
                "exchange_name": "binance",
                "status": "draft",
                "is_paper": True,
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"] == "Request validation failed"
    assert any(item["loc"][-1] == "name" for item in payload["errors"])


def test_create_bot_rejects_openapi_placeholder_display_fields(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        strategy_id = create_strategy(session).id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/bots",
            json={
                "name": "string",
                "strategy_id": strategy_id,
                "exchange_name": "string",
                "status": "draft",
                "is_paper": True,
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_create_bot_with_invalid_strategy_parameters_returns_validation_error(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        strategy = Strategy(
            name="Invalid Strategy",
            symbol="BTCUSDT",
            timeframe="1m",
            strategy_type="price_threshold",
            parameters={"buy_below": "10", "sell_above": "9", "quantity": "1"},
            is_active=True,
        )
        session.add(strategy)
        session.commit()
        strategy_id = strategy.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/bots",
            json={
                "name": "Invalid Strategy Bot",
                "strategy_id": strategy_id,
                "exchange_name": "binance",
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_strategy_parameters"
    assert response.json()["detail"] == "price_threshold sell_above must be greater than buy_below"


def test_create_bot_with_invalid_rsi_strategy_parameters_returns_validation_error(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        strategy = Strategy(
            name="Invalid RSI Strategy",
            symbol="BTCUSDT",
            timeframe="1m",
            strategy_type="rsi_threshold",
            parameters={"period": "14", "oversold": "70", "overbought": "70", "quantity": "1"},
            is_active=True,
        )
        session.add(strategy)
        session.commit()
        strategy_id = strategy.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/bots",
            json={
                "name": "Invalid RSI Strategy Bot",
                "strategy_id": strategy_id,
                "exchange_name": "binance",
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_strategy_parameters"
    assert response.json()["detail"] == "rsi_threshold oversold must be less than overbought"


def test_create_bot_with_invalid_bollinger_strategy_parameters_returns_validation_error(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        strategy = Strategy(
            name="Invalid Bollinger Strategy",
            symbol="BTCUSDT",
            timeframe="1m",
            strategy_type="bollinger_bands",
            parameters={"period": "1", "stddev_multiplier": "2", "quantity": "1"},
            is_active=True,
        )
        session.add(strategy)
        session.commit()
        strategy_id = strategy.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/bots",
            json={
                "name": "Invalid Bollinger Strategy Bot",
                "strategy_id": strategy_id,
                "exchange_name": "binance",
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_strategy_parameters"
    assert response.json()["detail"] == "bollinger_bands parameter period must be at least 2"


def test_create_bot_with_invalid_macd_strategy_parameters_returns_validation_error(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        strategy = Strategy(
            name="Invalid MACD Strategy",
            symbol="BTCUSDT",
            timeframe="1m",
            strategy_type="macd_crossover",
            parameters={"fast_period": "26", "slow_period": "12", "signal_period": "9", "quantity": "1"},
            is_active=True,
        )
        session.add(strategy)
        session.commit()
        strategy_id = strategy.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/bots",
            json={
                "name": "Invalid MACD Strategy Bot",
                "strategy_id": strategy_id,
                "exchange_name": "binance",
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_strategy_parameters"
    assert response.json()["detail"] == "macd_crossover fast_period must be less than slow_period"


def test_update_bot_basic_fields_returns_updated_bot(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        strategy_id = create_strategy(session).id
        other_strategy_id = create_strategy(session, name="Updated Strategy", symbol="ETHUSDT").id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/bots",
            json={
                "name": "Editable Bot",
                "strategy_id": strategy_id,
                "exchange_name": "binance",
                "status": "draft",
                "is_paper": True,
            },
        )
        bot_id = create_response.json()["id"]

        update_response = client.patch(
            f"/api/v1/bots/{bot_id}",
            json={
                "name": "Edited Bot",
                "strategy_id": other_strategy_id,
                "exchange_name": "kraken",
                "notes": "Updated from API test",
            },
        )

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert update_response.json()["id"] == bot_id
    assert update_response.json()["name"] == "Edited Bot"
    assert update_response.json()["strategy_id"] == other_strategy_id
    assert update_response.json()["exchange_name"] == "kraken"
    assert update_response.json()["notes"] == "Updated from API test"
    assert update_response.json()["status"] == "draft"


def test_update_bot_status_returns_updated_status(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        strategy_id = create_strategy(session).id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/bots",
            json={
                "name": "Status Bot",
                "strategy_id": strategy_id,
                "exchange_name": "binance",
                "status": "draft",
                "is_paper": True,
            },
        )
        bot_id = create_response.json()["id"]

        update_response = client.patch(
            f"/api/v1/bots/{bot_id}",
            json={"status": "paused"},
        )
        get_response = client.get(f"/api/v1/bots/{bot_id}")

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "paused"
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "paused"


def test_bot_list_includes_newly_created_bots_for_dashboard(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        btc_strategy_id = create_strategy(session, name="BTC Strategy", symbol="BTCUSDT").id
        eth_strategy_id = create_strategy(session, name="ETH Strategy", symbol="ETHUSDT").id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        first_create = client.post(
            "/api/v1/bots",
            json={
                "name": "BTC API Bot",
                "strategy_id": btc_strategy_id,
                "exchange_name": "binance",
                "status": "draft",
                "is_paper": True,
            },
        )
        second_create = client.post(
            "/api/v1/bots",
            json={
                "name": "ETH API Bot",
                "strategy_id": eth_strategy_id,
                "exchange_name": "binance",
                "status": "paused",
                "is_paper": True,
            },
        )
        list_response = client.get("/api/v1/bots")

    assert first_create.status_code == 201
    assert second_create.status_code == 201
    assert list_response.status_code == 200

    payload = list_response.json()
    assert set(payload) == {"items"}
    assert [item["name"] for item in payload["items"][:2]] == ["ETH API Bot", "BTC API Bot"]
    assert payload["items"][0]["status"] == "paused"
    assert payload["items"][1]["status"] == "draft"
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


def test_delete_bot_with_operational_history_cascades_owned_records(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        strategy, bot, profile = bot_stack_factory(session, status="active")
        assert profile is not None

        alert_rule = AlertRule(
            bot_id=bot.id,
            name="Risk Spike",
            field_name="last_price",
            operator="gt",
            threshold_value="100",
            severity="critical",
        )
        bot_run = BotRun(
            bot_id=bot.id,
            trigger_type="manual",
            status="running",
            summary="Bot runner active",
        )
        session.add_all([alert_rule, bot_run])
        session.commit()
        session.refresh(alert_rule)
        session.refresh(bot_run)

        run_event = RunEvent(
            bot_run_id=bot_run.id,
            event_type="lifecycle",
            level="info",
            message="Run started",
            payload={"source": "test"},
        )
        alert_event = AlertEvent(
            bot_id=bot.id,
            bot_run_id=bot_run.id,
            alert_rule_id=alert_rule.id,
            status="triggered",
            severity="critical",
            field_name="last_price",
            operator="gt",
            threshold_value="100",
            actual_value="125",
            title="Risk Spike",
            message="Price crossed threshold",
            triggered_at=datetime.now(timezone.utc),
        )
        session.add_all([run_event, alert_event])
        session.commit()

        bot_id = bot.id
        strategy_id = strategy.id
        profile_id = profile.id
        bot_run_id = bot_run.id
        run_event_id = run_event.id
        alert_rule_id = alert_rule.id
        alert_event_id = alert_event.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        delete_response = client.delete(f"/api/v1/bots/{bot_id}")
        get_response = client.get(f"/api/v1/bots/{bot_id}")
        list_response = client.get("/api/v1/bots")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
    assert get_response.json()["error_code"] == "bot_not_found"
    assert list_response.status_code == 200
    assert bot_id not in [item["bot_id"] for item in list_response.json()["items"]]

    with db_session_factory() as session:
        assert session.get(Strategy, strategy_id) is not None
        assert session.get(ExecutionProfile, profile_id) is None
        assert session.get(BotRun, bot_run_id) is None
        assert session.get(RunEvent, run_event_id) is None
        assert session.get(AlertRule, alert_rule_id) is None
        assert session.get(AlertEvent, alert_event_id) is None
        assert session.scalars(select(BotRun).where(BotRun.bot_id == bot_id)).all() == []
        assert session.scalars(select(AlertEvent).where(AlertEvent.bot_id == bot_id)).all() == []


def test_delete_bot_not_found_behavior_is_unchanged(
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        response = client.delete("/api/v1/bots/999999")

    assert response.status_code == 404
    assert response.json()["error_code"] == "bot_not_found"
