from decimal import Decimal

import httpx
from fastapi.testclient import TestClient

from app.api.v1.endpoints.market import get_binance_market_data_client
from app.main import app
from app.services.binance_market_data import BinanceMarketDataClient


def override_binance_client(handler):
    client = BinanceMarketDataClient(
        base_url="https://data-api.binance.vision",
        transport=httpx.MockTransport(handler),
    )
    app.dependency_overrides[get_binance_market_data_client] = lambda: client


def clear_binance_client_override() -> None:
    app.dependency_overrides.pop(get_binance_market_data_client, None)


def kline(open_time_ms: int = 1770000000000, close: str = "65050.00"):
    return [
        open_time_ms,
        "65000.00",
        "65100.00",
        "64950.00",
        close,
        "12.5",
        open_time_ms + 59999,
        "780000.00",
        100,
        "6.25",
        "390000.00",
        "0",
    ]


def test_binance_price_fetch_stores_latest_price(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"symbol": "BTCUSDT", "price": "65000.12"})

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/market/binance/price", json={"symbol": "BTCUSDT"})
    finally:
        clear_binance_client_override()

    latest = stub_market_data_service.get_latest("BTCUSDT")

    assert response.status_code == 200
    assert response.json()["symbol"] == "BTCUSDT"
    assert response.json()["price"] == "65000.12"
    assert response.json()["source"] == "binance"
    assert latest is not None
    assert latest.provider == "binance"
    assert latest.price == Decimal("65000.12")


def test_explicit_binance_price_fetch_overwrites_manual_price(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"symbol": "BTCUSDT", "price": "65000.12"})

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            manual_response = client.post("/api/v1/market/price", json={"symbol": "BTCUSDT", "price": "95"})
            binance_response = client.post("/api/v1/market/binance/price", json={"symbol": "BTCUSDT"})
    finally:
        clear_binance_client_override()

    latest = stub_market_data_service.get_latest("BTCUSDT")

    assert manual_response.status_code == 200
    assert manual_response.json()["price"] == "95"
    assert binance_response.status_code == 200
    assert binance_response.json()["price"] == "65000.12"
    assert latest is not None
    assert latest.provider == "binance"
    assert latest.price == Decimal("65000.12")


def test_binance_price_fetch_normalizes_lowercase_symbol(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    requested_symbols: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_symbols.append(request.url.params["symbol"])
        return httpx.Response(200, json={"symbol": "BTCUSDT", "price": "65000.12"})

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/market/binance/price", json={"symbol": "btcusdt"})
    finally:
        clear_binance_client_override()

    assert response.status_code == 200
    assert response.json()["symbol"] == "BTCUSDT"
    assert requested_symbols == ["BTCUSDT"]


def test_binance_price_fetch_network_error_returns_clean_api_error(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/market/binance/price", json={"symbol": "BTCUSDT"})
    finally:
        clear_binance_client_override()

    assert response.status_code == 502
    assert response.json()["error_code"] == "binance_market_data_error"
    assert response.json()["detail"] == "Could not reach Binance market data"


def test_binance_price_fetch_non_2xx_returns_clean_api_error(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(451, json={"msg": "Unavailable"})

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/market/binance/price", json={"symbol": "BTCUSDT"})
    finally:
        clear_binance_client_override()

    assert response.status_code == 502
    assert response.json()["error_code"] == "binance_market_data_error"
    assert response.json()["detail"] == "Binance market data request failed with status 451"


def test_binance_price_fetch_invalid_price_returns_clean_api_error(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"symbol": "BTCUSDT", "price": "not-a-price"})

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/market/binance/price", json={"symbol": "BTCUSDT"})
    finally:
        clear_binance_client_override()

    assert response.status_code == 502
    assert response.json()["error_code"] == "binance_market_data_error"
    assert response.json()["detail"] == "Binance market data returned an invalid price"


def test_manual_market_price_endpoint_still_works(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post("/api/v1/market/price", json={"symbol": "btcusdt", "price": "64000.00"})

    latest = stub_market_data_service.get_latest("BTCUSDT")

    assert response.status_code == 200
    assert response.json()["symbol"] == "BTCUSDT"
    assert response.json()["price"] == "64000.00"
    assert set(response.json()) == {"symbol", "price", "updated_at"}
    assert latest is not None
    assert latest.provider == "manual"


def test_binance_candle_fetch_stores_candles(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "BTCUSDT"
        assert request.url.params["interval"] == "1m"
        assert request.url.params["limit"] == "2"
        return httpx.Response(200, json=[kline(1770000000000), kline(1770000060000, close="65075.00")])

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/market/binance/candles",
                json={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 2},
            )
            list_response = client.get(
                "/api/v1/market/candles",
                params={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 10},
            )
    finally:
        clear_binance_client_override()

    assert response.status_code == 200
    assert response.json()["symbol"] == "BTCUSDT"
    assert response.json()["timeframe"] == "1m"
    assert response.json()["source"] == "binance"
    assert response.json()["requested_limit"] == 2
    assert response.json()["stored_count"] == 2
    assert [candle["close_price"] for candle in response.json()["candles"]] == [
        "65050.00000000",
        "65075.00000000",
    ]
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2


def test_binance_candle_fetch_normalizes_lowercase_symbol(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    requested_symbols: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_symbols.append(request.url.params["symbol"])
        return httpx.Response(200, json=[kline()])

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/market/binance/candles",
                json={"symbol": "btcusdt", "timeframe": "1m", "limit": 1},
            )
    finally:
        clear_binance_client_override()

    assert response.status_code == 200
    assert response.json()["symbol"] == "BTCUSDT"
    assert response.json()["candles"][0]["symbol"] == "BTCUSDT"
    assert requested_symbols == ["BTCUSDT"]


def test_binance_candle_fetch_upserts_duplicate_candles(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    responses = iter([
        [kline(close="65050.00")],
        [kline(close="65090.00")],
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses))

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            first_response = client.post(
                "/api/v1/market/binance/candles",
                json={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 1},
            )
            second_response = client.post(
                "/api/v1/market/binance/candles",
                json={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 1},
            )
            list_response = client.get(
                "/api/v1/market/candles",
                params={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 10},
            )
    finally:
        clear_binance_client_override()

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["candles"][0]["id"] == first_response.json()["candles"][0]["id"]
    assert second_response.json()["candles"][0]["close_price"] == "65090.00000000"
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["close_price"] == "65090.00000000"


def test_binance_candle_fetch_malformed_payload_returns_clean_api_error(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[["not-a-valid-kline"]])

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/market/binance/candles",
                json={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 1},
            )
    finally:
        clear_binance_client_override()

    assert response.status_code == 502
    assert response.json()["error_code"] == "binance_market_data_error"
    assert response.json()["detail"] == "Binance market data returned invalid candle data"


def test_binance_candle_fetch_non_2xx_returns_clean_api_error(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(451, json={"msg": "Unavailable"})

    override_binance_client(handler)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/market/binance/candles",
                json={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 1},
            )
    finally:
        clear_binance_client_override()

    assert response.status_code == 502
    assert response.json()["error_code"] == "binance_market_data_error"
    assert response.json()["detail"] == "Binance market data request failed with status 451"


def test_binance_candle_fetch_limit_validation_fails_cleanly(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/market/binance/candles",
            json={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 501},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"
