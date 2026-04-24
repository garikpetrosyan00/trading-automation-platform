from fastapi.testclient import TestClient

from app.main import app
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
