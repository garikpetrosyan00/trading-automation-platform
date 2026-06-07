from decimal import Decimal

import httpx
import pytest

from app.services.brokers.binance_exchange_info import (
    BinanceExchangeInfoClient,
    BinanceExchangeInfoError,
    BinanceExchangeInfoProvider,
    BinanceMarketOrderValidator,
)


def test_exchange_info_client_normalizes_success_and_uses_public_endpoint_without_credentials() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["api_key"] = request.headers.get("X-MBX-APIKEY")
        return httpx.Response(200, json=exchange_info_payload())

    client = BinanceExchangeInfoClient(
        base_url="https://testnet.binance.vision",
        transport=httpx.MockTransport(handler),
    )

    info = client.fetch_exchange_info()

    rules = info.get_symbol("btcusdt")
    assert captured["path"] == "/api/v3/exchangeInfo"
    assert captured["api_key"] is None
    assert rules is not None
    assert rules.symbol == "BTCUSDT"
    assert rules.base_asset == "BTC"
    assert rules.quote_asset == "USDT"
    assert rules.status == "TRADING"
    assert "MARKET" in rules.order_types
    assert rules.lot_size.min_qty == Decimal("0.001")
    assert rules.notional.max_notional == Decimal("10000")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"msg": "raw exchange body"}),
        httpx.Response(200, content=b"{"),
        httpx.Response(200, json={"bad": []}),
        httpx.Response(200, json={"symbols": [{"symbol": "BTCUSDT", "status": "TRADING", "filters": []}]}),
    ],
)
def test_exchange_info_client_errors_are_sanitized(response) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return response

    client = BinanceExchangeInfoClient(
        base_url="https://testnet.binance.vision",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BinanceExchangeInfoError) as exc_info:
        client.fetch_exchange_info()

    assert "raw exchange body" not in str(exc_info.value)


def test_exchange_info_client_network_failure_is_sanitized() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret-ish low level detail")

    client = BinanceExchangeInfoClient(
        base_url="https://testnet.binance.vision",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BinanceExchangeInfoError) as exc_info:
        client.fetch_exchange_info()

    assert "secret-ish" not in str(exc_info.value)


def test_exchange_info_provider_caches_success_until_ttl_and_does_not_cache_failures() -> None:
    class FakeClient:
        def __init__(self):
            self.calls = 0
            self.fail = False

        def fetch_exchange_info(self):
            self.calls += 1
            if self.fail:
                raise BinanceExchangeInfoError("sanitized")
            return BinanceExchangeInfoClient(
                base_url="https://testnet.binance.vision",
                transport=httpx.MockTransport(lambda _: httpx.Response(200, json=exchange_info_payload())),
            ).fetch_exchange_info()

    now = 100.0
    client = FakeClient()
    provider = BinanceExchangeInfoProvider(client, ttl_seconds=10, monotonic_provider=lambda: now)

    first = provider.get_exchange_info()
    second = provider.get_exchange_info()
    now = 111.0
    third = provider.get_exchange_info()
    client.fail = True
    now = 122.0

    with pytest.raises(BinanceExchangeInfoError):
        provider.get_exchange_info()
    with pytest.raises(BinanceExchangeInfoError):
        provider.get_exchange_info()

    assert first is second
    assert third is not second
    assert client.calls == 4


@pytest.mark.parametrize(
    ("payload_kwargs", "expected_reason"),
    [
        ({"symbol": "ETHUSDT"}, "testnet_symbol_not_found"),
        ({"status": "BREAK"}, "testnet_symbol_not_trading"),
        ({"order_types": ["LIMIT"]}, "testnet_market_order_not_supported"),
    ],
)
def test_symbol_validation_rejects_invalid_symbols(payload_kwargs, expected_reason) -> None:
    validator = validator_for_payload(exchange_info_payload(**payload_kwargs))

    decision = validator.validate(symbol="BTCUSDT", quantity=Decimal("0.01"), market_price=Decimal("100"))

    assert decision.allowed is False
    assert decision.reason == expected_reason


@pytest.mark.parametrize(
    ("quantity", "expected_reason"),
    [
        (Decimal("0.0001"), "testnet_quantity_below_minimum"),
        (Decimal("200"), "testnet_quantity_above_maximum"),
        (Decimal("0.0015"), "testnet_quantity_step_mismatch"),
    ],
)
def test_quantity_validation_lot_size(quantity, expected_reason) -> None:
    validator = validator_for_payload(exchange_info_payload())

    decision = validator.validate(symbol="BTCUSDT", quantity=quantity, market_price=Decimal("100"))

    assert decision.allowed is False
    assert decision.reason == expected_reason
    assert decision.metadata["filter_type"] == "LOT_SIZE"


def test_market_lot_size_is_applied_when_meaningful_and_zero_bounds_are_disabled() -> None:
    payload = exchange_info_payload(
        lot_size={"filterType": "LOT_SIZE", "minQty": "0", "maxQty": "0", "stepSize": "0"},
        market_lot_size={"filterType": "MARKET_LOT_SIZE", "minQty": "0.01", "maxQty": "0", "stepSize": "0.01"},
    )
    validator = validator_for_payload(payload)

    valid = validator.validate(symbol="BTCUSDT", quantity=Decimal("0.02"), market_price=Decimal("100"))
    invalid = validator.validate(symbol="BTCUSDT", quantity=Decimal("0.015"), market_price=Decimal("100"))

    assert valid.allowed is True
    assert invalid.reason == "testnet_quantity_step_mismatch"
    assert invalid.metadata["filter_type"] == "MARKET_LOT_SIZE"


@pytest.mark.parametrize(
    ("payload_kwargs", "quantity", "market_price", "expected_allowed", "expected_reason"),
    [
        (
            {"min_notional": "10", "min_notional_apply_to_market": True},
            Decimal("0.05"),
            Decimal("100"),
            False,
            "testnet_notional_below_minimum",
        ),
        ({"min_notional_apply_to_market": False}, Decimal("0.05"), Decimal("100"), True, "allowed"),
        (
            {"notional_min_notional": "10", "notional_apply_min_to_market": True},
            Decimal("0.05"),
            Decimal("100"),
            False,
            "testnet_notional_below_minimum",
        ),
        ({"notional_apply_max_to_market": True}, Decimal("2"), Decimal("6000"), False, "testnet_notional_above_maximum"),
        ({"notional_apply_max_to_market": False}, Decimal("2"), Decimal("6000"), True, "allowed"),
    ],
)
def test_notional_validation(payload_kwargs, quantity, market_price, expected_allowed, expected_reason) -> None:
    validator = validator_for_payload(exchange_info_payload(**payload_kwargs))

    decision = validator.validate(symbol="BTCUSDT", quantity=quantity, market_price=market_price)

    assert decision.allowed is expected_allowed
    assert decision.reason == expected_reason
    if not expected_allowed:
        assert decision.metadata["notional"] == str(quantity * market_price)


def validator_for_payload(payload: dict) -> BinanceMarketOrderValidator:
    client = BinanceExchangeInfoClient(
        base_url="https://testnet.binance.vision",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )
    return BinanceMarketOrderValidator(BinanceExchangeInfoProvider(client))


def exchange_info_payload(
    *,
    symbol: str = "BTCUSDT",
    status: str = "TRADING",
    order_types: list[str] | None = None,
    lot_size: dict | None = None,
    market_lot_size: dict | None = None,
    min_notional: str = "1",
    min_notional_apply_to_market: bool = True,
    notional_min_notional: str = "1",
    notional_apply_min_to_market: bool = False,
    notional_apply_max_to_market: bool = True,
) -> dict:
    return {
        "symbols": [
            {
                "symbol": symbol,
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "status": status,
                "orderTypes": order_types or ["LIMIT", "MARKET"],
                "filters": [
                    lot_size or {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "100", "stepSize": "0.001"},
                    market_lot_size
                    or {"filterType": "MARKET_LOT_SIZE", "minQty": "0", "maxQty": "0", "stepSize": "0"},
                    {
                        "filterType": "MIN_NOTIONAL",
                        "minNotional": min_notional,
                        "applyToMarket": min_notional_apply_to_market,
                    },
                    {
                        "filterType": "NOTIONAL",
                        "minNotional": notional_min_notional,
                        "maxNotional": "10000",
                        "applyMinToMarket": notional_apply_min_to_market,
                        "applyMaxToMarket": notional_apply_max_to_market,
                    },
                ],
            }
        ]
    }
