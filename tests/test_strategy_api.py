from fastapi.testclient import TestClient

from app.main import app


def test_create_strategy_with_parameters_returns_and_persists_them(
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    payload = {
        "name": "Price Threshold Strategy",
        "description": "Buy below and sell above configured prices.",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "parameters": {
            "buy_below": "60000",
            "sell_above": "65000",
            "quantity": "0.01",
        },
        "is_active": True,
    }

    with TestClient(app) as client:
        create_response = client.post("/api/v1/strategies", json=payload)
        created_strategy = create_response.json()
        get_response = client.get(f"/api/v1/strategies/{created_strategy['id']}")

    assert create_response.status_code == 201
    assert created_strategy["name"] == payload["name"]
    assert created_strategy["strategy_type"] == "price_threshold"
    assert created_strategy["parameters"] == payload["parameters"]
    assert get_response.status_code == 200
    assert get_response.json()["strategy_type"] == "price_threshold"
    assert get_response.json()["parameters"] == payload["parameters"]


def test_create_strategy_defaults_to_price_threshold(
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
            "/api/v1/strategies",
            json={
                "name": "Default Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
            },
        )

    assert response.status_code == 201
    assert response.json()["strategy_type"] == "price_threshold"
    assert response.json()["parameters"] == {}


def test_create_strategy_with_explicit_price_threshold_succeeds(
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
            "/api/v1/strategies",
            json={
                "name": "Explicit Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "price_threshold",
                "parameters": {
                    "buy_below": "60000",
                    "sell_above": "65000",
                    "quantity": "0.01",
                },
            },
        )

    assert response.status_code == 201
    assert response.json()["strategy_type"] == "price_threshold"


def test_create_strategy_with_unsupported_strategy_type_fails_cleanly(
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
            "/api/v1/strategies",
            json={
                "name": "RSI Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "rsi",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_create_price_threshold_strategy_with_invalid_parameters_fails_cleanly(
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    invalid_payloads = [
        {
            "buy_below": "not-a-number",
            "sell_above": "65000",
            "quantity": "0.01",
        },
        {
            "buy_below": "65000",
            "sell_above": "60000",
            "quantity": "0.01",
        },
        {
            "buy_below": "60000",
            "sell_above": "65000",
            "quantity": "0",
        },
        {
            "buy_below": "60000",
            "quantity": "0.01",
        },
    ]

    with TestClient(app) as client:
        for parameters in invalid_payloads:
            response = client.post(
                "/api/v1/strategies",
                json={
                    "name": "Invalid Strategy",
                    "symbol": "BTCUSDT",
                    "timeframe": "1m",
                    "strategy_type": "price_threshold",
                    "parameters": parameters,
                },
            )

            assert response.status_code == 422
            assert response.json()["detail"] == "Request validation failed"


def test_update_strategy_parameters_returns_and_persists_them(
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/strategies",
            json={
                "name": "Price Threshold Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "parameters": {
                    "buy_below": "60000",
                    "sell_above": "65000",
                    "quantity": "0.01",
                },
            },
        )
        strategy_id = create_response.json()["id"]

        update_response = client.patch(
            f"/api/v1/strategies/{strategy_id}",
            json={
                "parameters": {
                    "buy_below": "59000",
                    "sell_above": "66000",
                    "quantity": "0.02",
                },
            },
        )
        get_response = client.get(f"/api/v1/strategies/{strategy_id}")

    expected_parameters = {
        "buy_below": "59000",
        "sell_above": "66000",
        "quantity": "0.02",
    }

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert update_response.json()["strategy_type"] == "price_threshold"
    assert update_response.json()["parameters"] == expected_parameters
    assert get_response.status_code == 200
    assert get_response.json()["parameters"] == expected_parameters
