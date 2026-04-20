from app.data.providers.binance import BinanceMarketDataProvider
from app.data.schemas import MarketEventType


def test_binance_provider_normalizes_ticker_payload() -> None:
    provider = BinanceMarketDataProvider(
        symbol="BTCUSDT",
        websocket_url="wss://stream.binance.com:9443/ws",
    )
    payload = {
        "e": "24hrTicker",
        "E": 1713571200123,
        "s": "BTCUSDT",
        "b": "64000.10",
        "a": "64000.20",
        "o": "63000.00",
        "h": "65000.00",
        "l": "62000.00",
        "c": "64010.50",
        "v": "123.456",
    }

    event = provider.parse_payload(payload)

    assert event.provider == "binance"
    assert event.symbol == "BTCUSDT"
    assert event.event_type == MarketEventType.TICKER
    assert str(event.price) == "64010.50"
    assert str(event.bid) == "64000.10"
    assert str(event.ask) == "64000.20"
    assert str(event.open) == "63000.00"
    assert str(event.high) == "65000.00"
    assert str(event.low) == "62000.00"
    assert str(event.close) == "64010.50"
    assert str(event.volume) == "123.456"


def test_binance_provider_rejects_invalid_payload() -> None:
    provider = BinanceMarketDataProvider(
        symbol="BTCUSDT",
        websocket_url="wss://stream.binance.com:9443/ws",
    )

    try:
        provider.parse_payload({"s": "BTCUSDT"})
    except ValueError as exc:
        assert str(exc) == "Invalid Binance ticker payload"
    else:
        raise AssertionError("Expected ValueError for invalid payload")
