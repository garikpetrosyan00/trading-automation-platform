from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.models.market_candle import MarketCandle
from app.models.strategy import Strategy


def create_moving_average_strategy(session, *, parameters: dict | None = None, timeframe: str = "1m") -> Strategy:
    strategy = Strategy(
        name="MA Cross Backtest",
        symbol="BTCUSDT",
        timeframe=timeframe,
        strategy_type="moving_average_cross",
        parameters=parameters
        if parameters is not None
        else {
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


def create_price_threshold_strategy(session) -> Strategy:
    strategy = Strategy(
        name="Price Threshold Backtest",
        symbol="BTCUSDT",
        timeframe="1m",
        strategy_type="price_threshold",
        parameters={
            "buy_below": "11",
            "sell_above": "19",
            "quantity": "1",
        },
        is_active=True,
    )
    session.add(strategy)
    session.commit()
    session.refresh(strategy)
    return strategy


def add_candles(session, *, closes: list[str], source: str = "manual", timeframe: str = "1m") -> None:
    start = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)
    for index, close in enumerate(closes):
        close_price = Decimal(close)
        open_time = start + timedelta(minutes=index)
        session.add(
            MarketCandle(
                symbol="BTCUSDT",
                timeframe=timeframe,
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
    assert body["closed_trades"] == 1
    assert body["open_position"] is False
    assert body["winning_trades"] == 0
    assert body["losing_trades"] == 1
    assert body["total_return"] == "-10.00000000"
    assert body["total_return_percent"] == "-10.00000000"
    assert body["win_rate"] == "0"
    assert body["average_trade_pnl"] == "-10.00000000"
    assert body["best_trade_pnl"] == "-10.00000000"
    assert body["worst_trade_pnl"] == "-10.00000000"
    assert body["profit_factor"] == "0"
    assert len(body["trades"]) == body["number_of_trades"]
    assert [trade["side"] for trade in body["trades"]] == ["buy", "sell"]
    assert [trade["decision"] for trade in body["trades"]] == ["buy", "sell"]
    assert body["trades"][0]["price"] == "20.00000000"
    assert body["trades"][0]["cash_balance"] == "80.00000000"
    assert body["trades"][0]["position_quantity"] == "1"
    assert body["trades"][0]["decision_reason"] == "short moving average crossed above long moving average"
    assert body["trades"][1]["realized_pnl"] == "-10.00000000"
    assert body["trades"][1]["cash_balance"] == "90.00000000"
    assert body["trades"][1]["position_quantity"] == "0"
    assert body["trades"][1]["decision_reason"] == "short moving average crossed below long moving average"


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
    assert body["closed_trades"] == 0
    assert body["open_position"] is False
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
        "closed_trades",
        "open_position",
        "winning_trades",
        "losing_trades",
        "total_return",
        "total_return_percent",
        "win_rate",
        "average_trade_pnl",
        "best_trade_pnl",
        "worst_trade_pnl",
        "profit_factor",
        "trades",
    }
    assert expected_keys <= set(body)
    assert body["final_balance"] == "105.00000000"
    assert body["realized_pnl"] == "0"
    assert body["unrealized_pnl"] == "5.00000000"
    assert body["total_return"] == "5.00000000"
    assert body["total_return_percent"] == "5.00000000"
    assert body["win_rate"] is None
    assert body["average_trade_pnl"] is None
    assert body["best_trade_pnl"] is None
    assert body["worst_trade_pnl"] is None
    assert body["profit_factor"] is None
    assert body["number_of_trades"] == 1
    assert body["closed_trades"] == 0
    assert body["open_position"] is True
    assert body["position_quantity"] == "1"
    assert body["entry_price"] == "20.00000000"
    assert len(body["trades"]) == 1
    assert len(body["trades"]) == body["number_of_trades"]
    assert body["trades"][0]["decision"] == "buy"
    assert body["trades"][0]["side"] == "buy"
    assert body["trades"][0]["price"] == "20.00000000"
    assert body["trades"][0]["quantity"] == "1"
    assert body["trades"][0]["cash_balance"] == "80.00000000"
    assert body["trades"][0]["position_quantity"] == "1"
    assert body["trades"][0]["realized_pnl"] == "0"
    assert body["trades"][0]["decision_reason"] == "short moving average crossed above long moving average"


def test_run_moving_average_cross_backtest_with_source_through_api(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_moving_average_strategy(db_session, timeframe="5m")
    add_candles(db_session, closes=["10", "11", "12", "13"], source="manual", timeframe="5m")
    add_candles(db_session, closes=["10", "10", "10", "20", "25"], source="binance", timeframe="5m")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests",
            json={"strategy_id": strategy.id, "initial_balance": "100", "source": "binance"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == strategy.id
    assert body["strategy_type"] == "moving_average_cross"
    assert body["symbol"] == "BTCUSDT"
    assert body["timeframe"] == "5m"
    assert body["source"] == "binance"
    assert body["initial_balance"] == "100"
    assert body["final_balance"] == "105.00000000"
    assert body["number_of_trades"] == 1
    assert body["closed_trades"] == 0
    assert body["realized_pnl"] == "0"
    assert body["unrealized_pnl"] == "5.00000000"
    assert body["trades"][0]["side"] == "buy"


def test_run_backtest_with_invalid_moving_average_parameters_is_safe_through_api(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_moving_average_strategy(
        db_session,
        parameters={
            "short_window": "3",
            "long_window": "3",
            "quantity": "1",
        },
    )
    add_candles(db_session, closes=["10", "10", "10", "20"])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests",
            json={"strategy_id": strategy.id, "initial_balance": "100", "source": "manual"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == strategy.id
    assert body["strategy_type"] == "moving_average_cross"
    assert body["symbol"] == "BTCUSDT"
    assert body["timeframe"] == "1m"
    assert body["source"] == "manual"
    assert body["initial_balance"] == "100"
    assert body["final_balance"] == "100.00000000"
    assert body["number_of_trades"] == 0
    assert body["closed_trades"] == 0
    assert body["realized_pnl"] == "0"
    assert body["unrealized_pnl"] == "0"
    assert body["trades"] == []


def test_run_price_threshold_backtest_behavior_is_preserved_through_api(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_price_threshold_strategy(db_session)
    add_candles(db_session, closes=["10", "20"])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests",
            json={"strategy_id": strategy.id, "initial_balance": "100", "source": "manual"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == strategy.id
    assert body["strategy_type"] == "price_threshold"
    assert body["symbol"] == "BTCUSDT"
    assert body["timeframe"] == "1m"
    assert body["source"] == "manual"
    assert body["initial_balance"] == "100"
    assert body["final_balance"] == "110.00000000"
    assert body["number_of_trades"] == 2
    assert body["closed_trades"] == 1
    assert body["realized_pnl"] == "10.00000000"
    assert body["unrealized_pnl"] == "0"
    assert body["total_return"] == "10.00000000"
    assert body["total_return_percent"] == "10.00000000"
    assert body["win_rate"] == "100"
    assert body["average_trade_pnl"] == "10.00000000"
    assert body["best_trade_pnl"] == "10.00000000"
    assert body["worst_trade_pnl"] == "10.00000000"
    assert body["profit_factor"] is None
    assert [trade["side"] for trade in body["trades"]] == ["buy", "sell"]
    assert [trade["decision"] for trade in body["trades"]] == ["buy", "sell"]
    assert body["trades"][0]["price"] == "10.00000000"
    assert body["trades"][0]["cash_balance"] == "90.00000000"
    assert body["trades"][0]["position_quantity"] == "1"
    assert body["trades"][0]["decision_reason"] == "price is below strategy buy_below"
    assert body["trades"][1]["price"] == "20.00000000"
    assert body["trades"][1]["cash_balance"] == "110.00000000"
    assert body["trades"][1]["position_quantity"] == "0"
    assert body["trades"][1]["realized_pnl"] == "10.00000000"
    assert body["trades"][1]["decision_reason"] == "price is above strategy sell_above and position exists"


def test_optimize_price_threshold_backtest_ranks_parameter_sets_and_does_not_mutate_strategy(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_price_threshold_strategy(db_session)
    original_parameters = dict(strategy.parameters)
    add_candles(db_session, closes=["10", "20"])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests/optimize",
            json={
                "strategy_id": strategy.id,
                "initial_balance": "100",
                "source": "manual",
                "parameter_sets": [
                    {"buy_below": "11", "sell_above": "19", "quantity": "1"},
                    {"buy_below": "9", "sell_above": "19", "quantity": "1"},
                    {"entry_below": "11", "exit_above": "19", "quantity": "2"},
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == strategy.id
    assert body["symbol"] == "BTCUSDT"
    assert body["timeframe"] == "1m"
    assert body["strategy_type"] == "price_threshold"
    assert body["source"] == "manual"
    assert body["initial_balance"] == "100"
    assert body["total_runs"] == 3
    assert [result["rank"] for result in body["results"]] == [1, 2, 3]
    assert body["results"][0]["parameters"] == {"buy_below": "11", "sell_above": "19", "quantity": "2"}
    assert body["results"][0]["total_return_percent"] == "20.00000000"
    assert body["results"][1]["parameters"] == {"buy_below": "11", "sell_above": "19", "quantity": "1"}
    assert body["results"][1]["total_return_percent"] == "10.00000000"
    assert body["results"][2]["number_of_trades"] == 0
    assert body["results"][2]["closed_trades"] == 0

    db_session.refresh(strategy)
    assert strategy.parameters == original_parameters


def test_optimize_moving_average_cross_backtest_ranks_parameter_sets(
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
            "/api/v1/backtests/optimize",
            json={
                "strategy_id": strategy.id,
                "initial_balance": "100",
                "source": "manual",
                "parameter_sets": [
                    {"short_window": "2", "long_window": "3", "quantity": "1"},
                    {"short_window": "2", "long_window": "4", "quantity": "1"},
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_type"] == "moving_average_cross"
    assert body["total_runs"] == 2
    assert body["results"][0]["rank"] == 1
    assert body["results"][0]["parameters"] == {"short_window": "2", "long_window": "3", "quantity": "1"}
    assert body["results"][0]["total_return_percent"] == "5.00000000"
    assert body["results"][1]["number_of_trades"] == 0


def test_optimize_backtest_rejects_empty_parameter_sets(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_price_threshold_strategy(db_session)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests/optimize",
            json={
                "strategy_id": strategy.id,
                "initial_balance": "100",
                "parameter_sets": [],
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_optimize_backtest_rejects_too_many_parameter_sets(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_price_threshold_strategy(db_session)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests/optimize",
            json={
                "strategy_id": strategy.id,
                "initial_balance": "100",
                "parameter_sets": [
                    {"buy_below": "11", "sell_above": "19", "quantity": "1"}
                    for _ in range(51)
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_optimize_backtest_rejects_invalid_moving_average_windows(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_moving_average_strategy(db_session)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/backtests/optimize",
            json={
                "strategy_id": strategy.id,
                "initial_balance": "100",
                "parameter_sets": [
                    {"short_window": "5", "long_window": "5", "quantity": "1"},
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_optimization_parameters"
