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
    assert latest.provider == "stub"
