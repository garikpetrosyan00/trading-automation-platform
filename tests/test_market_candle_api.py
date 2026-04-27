from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app


def candle_payload(**overrides):
    base = {
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "open_time": datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc).isoformat(),
        "close_time": datetime(2026, 4, 28, 12, 1, tzinfo=timezone.utc).isoformat(),
        "open_price": "65000.00",
        "high_price": "65100.00",
        "low_price": "64950.00",
        "close_price": "65050.00",
        "volume": "12.5",
        "source": "manual",
    }
    base.update(overrides)
    return base


def test_create_market_candle_succeeds(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post("/api/v1/market/candles", json=candle_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["symbol"] == "BTCUSDT"
    assert body["timeframe"] == "1m"
    assert body["open_price"] == "65000.00000000"
    assert body["source"] == "manual"
    assert "created_at" in body


def test_create_market_candle_normalizes_symbol(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post("/api/v1/market/candles", json=candle_payload(symbol="btcusdt"))

    assert response.status_code == 201
    assert response.json()["symbol"] == "BTCUSDT"


def test_list_market_candles_returns_recent_limit_oldest_first(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    start = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)

    with TestClient(app) as client:
        for index in range(3):
            open_time = start + timedelta(minutes=index)
            response = client.post(
                "/api/v1/market/candles",
                json=candle_payload(
                    open_time=open_time.isoformat(),
                    close_time=(open_time + timedelta(minutes=1)).isoformat(),
                    close_price=str(65050 + index),
                ),
            )
            assert response.status_code == 201

        list_response = client.get(
            "/api/v1/market/candles",
            params={"symbol": "btcusdt", "timeframe": "1m", "limit": 2},
        )

    assert list_response.status_code == 200
    candles = list_response.json()
    assert [candle["close_price"] for candle in candles] == ["65051.00000000", "65052.00000000"]
    assert candles[0]["open_time"] < candles[1]["open_time"]


def test_duplicate_market_candle_updates_existing_row(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        first_response = client.post("/api/v1/market/candles", json=candle_payload(close_price="65050.00"))
        second_response = client.post("/api/v1/market/candles", json=candle_payload(close_price="65075.00"))
        list_response = client.get(
            "/api/v1/market/candles",
            params={"symbol": "BTCUSDT", "timeframe": "1m"},
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()["id"] == first_response.json()["id"]
    assert second_response.json()["close_price"] == "65075.00000000"
    assert len(list_response.json()) == 1


def test_create_market_candle_with_invalid_price_relationship_fails_cleanly(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post("/api/v1/market/candles", json=candle_payload(high_price="64900.00"))

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_list_market_candles_with_invalid_limit_fails_cleanly(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/market/candles",
            params={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 501},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"
