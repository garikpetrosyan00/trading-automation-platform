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


def test_create_strategy_rejects_openapi_placeholder_display_fields(
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
                "name": "string",
                "symbol": "string",
                "timeframe": "string",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_create_moving_average_cross_strategy_with_valid_parameters_succeeds(
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    payload = {
        "name": "Moving Average Cross Strategy",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "strategy_type": "moving_average_cross",
        "parameters": {
            "short_window": 9,
            "long_window": 21,
            "quantity": "0.01",
        },
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/strategies", json=payload)

    assert response.status_code == 201
    assert response.json()["strategy_type"] == "moving_average_cross"
    assert response.json()["parameters"] == payload["parameters"]


def test_create_moving_average_cross_strategy_with_invalid_window_order_fails_cleanly(
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
                "name": "Invalid MA Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "moving_average_cross",
                "parameters": {
                    "short_window": 21,
                    "long_window": 21,
                    "quantity": "0.01",
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_strategy_parameters"
    assert response.json()["detail"] == "moving_average_cross short_window must be less than long_window"


def test_create_moving_average_cross_strategy_with_non_integer_window_fails_cleanly(
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
                "name": "Invalid MA Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "moving_average_cross",
                "parameters": {
                    "short_window": "9.5",
                    "long_window": 21,
                    "quantity": "0.01",
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_strategy_parameters"
    assert response.json()["detail"] == "moving_average_cross parameter short_window must be a positive integer"


def test_create_moving_average_cross_strategy_with_non_positive_window_fails_cleanly(
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
                "name": "Invalid MA Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "moving_average_cross",
                "parameters": {
                    "short_window": 9,
                    "long_window": 0,
                    "quantity": "0.01",
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_strategy_parameters"
    assert response.json()["detail"] == "moving_average_cross parameter long_window must be a positive integer"


def test_create_moving_average_cross_strategy_with_non_positive_quantity_fails_cleanly(
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
                "name": "Invalid MA Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "moving_average_cross",
                "parameters": {
                    "short_window": 9,
                    "long_window": 21,
                    "quantity": "0",
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_strategy_parameters"
    assert response.json()["detail"] == "moving_average_cross parameter quantity must be a positive number"


def test_create_rsi_threshold_strategy_with_valid_parameters_succeeds(
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    payload = {
        "name": "RSI Threshold Strategy",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "strategy_type": "rsi_threshold",
        "parameters": {
            "period": 14,
            "oversold": "30",
            "overbought": "70",
            "quantity": "0.01",
        },
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/strategies", json=payload)

    assert response.status_code == 201
    assert response.json()["strategy_type"] == "rsi_threshold"
    assert response.json()["parameters"] == payload["parameters"]


def test_create_rsi_threshold_strategy_with_invalid_parameters_fails_cleanly(
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
                "name": "Invalid RSI Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "rsi_threshold",
                "parameters": {
                    "period": "14.5",
                    "oversold": "30",
                    "overbought": "70",
                    "quantity": "0.01",
                },
            },
        )
        range_response = client.post(
            "/api/v1/strategies",
            json={
                "name": "Invalid RSI Range Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "rsi_threshold",
                "parameters": {
                    "period": 14,
                    "oversold": "75",
                    "overbought": "70",
                    "quantity": "0.01",
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_strategy_parameters"
    assert response.json()["detail"] == "rsi_threshold parameter period must be a positive integer"
    assert range_response.status_code == 422
    assert range_response.json()["error_code"] == "invalid_strategy_parameters"
    assert range_response.json()["detail"] == "rsi_threshold oversold must be less than overbought"


def test_create_bollinger_bands_strategy_with_valid_parameters_succeeds(
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    payload = {
        "name": "Bollinger Bands Strategy",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "strategy_type": "bollinger_bands",
        "parameters": {
            "period": 20,
            "stddev_multiplier": "2",
            "quantity": "0.01",
        },
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/strategies", json=payload)

    assert response.status_code == 201
    assert response.json()["strategy_type"] == "bollinger_bands"
    assert response.json()["parameters"] == payload["parameters"]


def test_create_bollinger_bands_strategy_with_invalid_parameters_fails_cleanly(
    stub_market_data_service,
    bot_runner_factory,
    configure_app_state,
) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        period_response = client.post(
            "/api/v1/strategies",
            json={
                "name": "Invalid Bollinger Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "bollinger_bands",
                "parameters": {
                    "period": 1,
                    "stddev_multiplier": "2",
                    "quantity": "0.01",
                },
            },
        )
        multiplier_response = client.post(
            "/api/v1/strategies",
            json={
                "name": "Invalid Bollinger Multiplier Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "bollinger_bands",
                "parameters": {
                    "period": 20,
                    "stddev_multiplier": "0",
                    "quantity": "0.01",
                },
            },
        )

    assert period_response.status_code == 422
    assert period_response.json()["error_code"] == "invalid_strategy_parameters"
    assert period_response.json()["detail"] == "bollinger_bands parameter period must be at least 2"
    assert multiplier_response.status_code == 422
    assert multiplier_response.json()["error_code"] == "invalid_strategy_parameters"
    assert (
        multiplier_response.json()["detail"]
        == "bollinger_bands parameter stddev_multiplier must be a positive number"
    )


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
            "buy_below": "-1",
            "sell_above": "65000",
            "quantity": "0.01",
        },
        {
            "buy_below": "60000",
            "sell_above": "0",
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
            "sell_above": "65000",
            "quantity": "-0.01",
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
            assert response.json()["error_code"] == "invalid_strategy_parameters"


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


def test_update_price_threshold_strategy_rejects_invalid_parameters(
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
                    "buy_below": "60000",
                    "sell_above": "60000",
                    "quantity": "0.02",
                },
            },
        )

    assert create_response.status_code == 201
    assert update_response.status_code == 422
    assert update_response.json()["error_code"] == "invalid_strategy_parameters"
    assert update_response.json()["detail"] == "price_threshold sell_above must be greater than buy_below"


def test_update_moving_average_cross_strategy_rejects_invalid_parameters(
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
                "name": "Moving Average Cross Strategy",
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "strategy_type": "moving_average_cross",
                "parameters": {
                    "short_window": 9,
                    "long_window": 21,
                    "quantity": "0.01",
                },
            },
        )
        strategy_id = create_response.json()["id"]
        update_response = client.patch(
            f"/api/v1/strategies/{strategy_id}",
            json={
                "parameters": {
                    "short_window": 21,
                    "long_window": 21,
                    "quantity": "0.02",
                },
            },
        )

    assert create_response.status_code == 201
    assert update_response.status_code == 422
    assert update_response.json()["error_code"] == "invalid_strategy_parameters"
    assert update_response.json()["detail"] == "moving_average_cross short_window must be less than long_window"


def test_update_strategy_allows_valid_partial_parameters(
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
            json={"parameters": {"quantity": "0.02"}},
        )

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert update_response.json()["parameters"] == {"quantity": "0.02"}
