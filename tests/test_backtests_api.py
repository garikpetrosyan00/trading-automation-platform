from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.models.market_candle import MarketCandle
from app.models.strategy import Strategy


def create_moving_average_strategy(session) -> Strategy:
    strategy = Strategy(
        name="MA Cross Backtest",
        symbol="BTCUSDT",
        timeframe="1m",
        strategy_type="moving_average_cross",
        parameters={
            "short_window": "2",
            "long_window": "3",
            "quantity": "1",
        },
        is_active=True,
    )
    session.add(strategy)
    session.commit()
    session.refresh(strategy)
    return strategy


def add_candles(session, *, closes: list[str], source: str = "manual") -> None:
    start = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)
    for index, close in enumerate(closes):
        close_price = Decimal(close)
        open_time = start + timedelta(minutes=index)
        session.add(
            MarketCandle(
                symbol="BTCUSDT",
                timeframe="1m",
                open_time=open_time,
                close_time=open_time + timedelta(minutes=1),
                open_price=close_price,
                high_price=close_price,
                low_price=close_price,
                close_price=close_price,
                volume=Decimal("1"),
                source=source,
            )
        )
    session.commit()


def test_run_backtest_returns_structured_result(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_moving_average_strategy(db_session)
    add_candles(db_session, closes=["10", "10", "10", "20", "20", "20", "20", "10"])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests",
            json={"strategy_id": strategy.id, "initial_balance": "100", "source": "manual"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == strategy.id
    assert body["symbol"] == "BTCUSDT"
    assert body["timeframe"] == "1m"
    assert body["strategy_type"] == "moving_average_cross"
    assert body["source"] == "manual"
    assert body["initial_balance"] == "100"
    assert body["final_balance"] == "90.00000000"
    assert body["realized_pnl"] == "-10.00000000"
    assert body["unrealized_pnl"] == "0"
    assert body["number_of_trades"] == 2
    assert body["winning_trades"] == 0
    assert body["losing_trades"] == 1
    assert [trade["side"] for trade in body["trades"]] == ["buy", "sell"]
    assert body["trades"][0]["price"] == "20.00000000"
    assert body["trades"][1]["realized_pnl"] == "-10.00000000"


def test_run_backtest_missing_strategy_returns_404(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests",
            json={"strategy_id": 999, "initial_balance": "100"},
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "strategy_not_found"


def test_run_backtest_insufficient_candles_returns_no_trade_result(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_moving_average_strategy(db_session)
    add_candles(db_session, closes=["10", "10", "20"])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests",
            json={"strategy_id": strategy.id, "initial_balance": "100"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["candles_processed"] == 3
    assert body["number_of_trades"] == 0
    assert body["cash_balance"] == "100"
    assert body["position_quantity"] == "0"
    assert body["final_balance"] == "100.00000000"
    assert body["realized_pnl"] == "0"
    assert body["trades"] == []


def test_run_backtest_response_includes_balances_pnl_trade_counts_and_trades(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_moving_average_strategy(db_session)
    add_candles(db_session, closes=["10", "10", "10", "20", "25"])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests",
            json={"strategy_id": strategy.id, "initial_balance": "100"},
        )

    assert response.status_code == 200
    body = response.json()
    expected_keys = {
        "final_balance",
        "realized_pnl",
        "unrealized_pnl",
        "number_of_trades",
        "winning_trades",
        "losing_trades",
        "trades",
    }
    assert expected_keys <= set(body)
    assert body["final_balance"] == "105.00000000"
    assert body["realized_pnl"] == "0"
    assert body["unrealized_pnl"] == "5.00000000"
    assert body["number_of_trades"] == 1
    assert len(body["trades"]) == 1
