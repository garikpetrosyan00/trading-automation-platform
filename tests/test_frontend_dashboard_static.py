from pathlib import Path


FRONTEND_APP = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def test_dashboard_startup_does_not_auto_fetch_binance_live_market_prices() -> None:
    source = FRONTEND_APP.read_text()
    startup_block = source.rsplit("document.documentElement.lang", 1)[1]

    assert "refreshLiveMarket();" not in startup_block


def test_dashboard_keeps_explicit_binance_price_controls() -> None:
    source = FRONTEND_APP.read_text()

    assert 'binancePriceFetch.addEventListener("click", fetchBinancePriceForSelectedBot)' in source
    assert 'liveMarketRefresh.addEventListener("click", refreshLiveMarket)' in source
    assert 'fetchJson("/api/v1/market/binance/price"' in source
