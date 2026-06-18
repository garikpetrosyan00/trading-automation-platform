from pathlib import Path


FRONTEND_APP = Path(__file__).resolve().parents[1] / "frontend" / "app.js"
FRONTEND_INDEX = Path(__file__).resolve().parents[1] / "frontend" / "index.html"


def test_dashboard_startup_does_not_auto_fetch_binance_live_market_prices() -> None:
    source = FRONTEND_APP.read_text()
    startup_block = source.rsplit("document.documentElement.lang", 1)[1]

    assert "refreshLiveMarket();" not in startup_block


def test_dashboard_keeps_explicit_binance_price_controls() -> None:
    source = FRONTEND_APP.read_text()

    assert 'binancePriceFetch.addEventListener("click", fetchBinancePriceForSelectedBot)' in source
    assert 'liveMarketRefresh.addEventListener("click", refreshLiveMarket)' in source
    assert 'fetchJson("/api/v1/market/binance/price"' in source


def test_paper_position_card_is_adjacent_to_paper_portfolio_and_draft_balance() -> None:
    source = FRONTEND_INDEX.read_text()

    portfolio_index = source.index('class="paper-portfolio-panel"')
    position_index = source.index('class="paper-position-panel"')
    draft_balance_index = source.index('class="draft-balance-panel"')

    assert portfolio_index < position_index < draft_balance_index
    assert 'id="paper-position-content"' in source
    assert "button" not in source[position_index:draft_balance_index]


def test_paper_position_uses_selected_bot_read_endpoint_in_shared_refresh_paths() -> None:
    source = FRONTEND_APP.read_text()

    assert source.count("/paper-position`)") == 3
    assert "normalizePaperPosition" in source
    assert "applyPaperPositionResult" in source
    assert "clearPaperPosition" in source
    assert "renderPaperPosition();" in source
    assert 'method: "POST"' not in "\n".join(
        line for line in source.splitlines() if "paper-position" in line
    )


def test_paper_position_normalizer_and_renderer_keep_a_public_field_allowlist() -> None:
    source = FRONTEND_APP.read_text()
    normalizer = source[
        source.index("function normalizePaperPosition"):
        source.index("function normalizePaperOrder")
    ]
    renderer = source[
        source.index("function renderPaperPosition"):
        source.index("function renderDraftBalance")
    ]

    for field in (
        "symbol",
        "base_asset",
        "quote_asset",
        "quantity",
        "average_entry_price",
        "realized_pnl",
        "market_price",
        "unrealized_pnl",
        "position_value",
        "updated_at",
    ):
        assert field in normalizer

    for forbidden in (
        "order_id",
        "fill_id",
        "execution_attempt",
        "reconciliation",
        "metadata",
        "secret",
        "broker",
    ):
        assert forbidden not in normalizer
        assert forbidden not in renderer

    assert 't("paper_position_local_price_unavailable")' in renderer
