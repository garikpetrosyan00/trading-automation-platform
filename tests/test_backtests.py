from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.backtest_run import BacktestRun
from app.models.market_candle import MarketCandle
from app.models.strategy import Strategy


def create_moving_average_strategy(session, *, symbol: str = "BTCUSDT") -> Strategy:
    strategy = Strategy(
        name=f"{symbol} MA Cross Backtest",
        symbol=symbol,
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


def add_candles(session, *, symbol: str = "BTCUSDT", closes: list[str], source: str = "manual") -> None:
    start = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)
    for index, close in enumerate(closes):
        close_price = Decimal(close)
        open_time = start + timedelta(minutes=index)
        session.add(
            MarketCandle(
                symbol=symbol,
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


def test_post_backtest_persists_result(
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
            json={"strategy_id": strategy.id, "initial_balance": "100", "source": "manual"},
        )

    assert response.status_code == 200
    body = response.json()

    db_session.expire_all()
    persisted_runs = list(db_session.scalars(select(BacktestRun)).all())
    assert len(persisted_runs) == 1
    persisted = persisted_runs[0]
    assert persisted.strategy_id == strategy.id
    assert persisted.symbol == body["symbol"]
    assert persisted.timeframe == body["timeframe"]
    assert persisted.strategy_type == body["strategy_type"]
    assert persisted.source == body["source"]
    assert persisted.initial_balance == Decimal("100.00000000")
    assert persisted.final_balance == Decimal(body["final_balance"])
    assert persisted.number_of_trades == body["number_of_trades"]
    assert persisted.closed_trades == body["closed_trades"]
    assert persisted.open_position == body["open_position"]
    assert persisted.position_quantity == Decimal(body["position_quantity"])


def test_get_backtests_returns_persisted_results_newest_first(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    strategy = create_moving_average_strategy(db_session)
    add_candles(db_session, closes=["10", "10", "10", "20", "25"])

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/backtests",
            json={"strategy_id": strategy.id, "initial_balance": "100", "source": "manual"},
        )
        second = client.post(
            "/api/v1/backtests",
            json={"strategy_id": strategy.id, "initial_balance": "200", "source": "manual"},
        )
        response = client.get("/api/v1/backtests")

    assert first.status_code == 200
    assert second.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] > body[1]["id"]
    assert body[0]["created_at"] is not None
    assert body[0]["initial_balance"] == "200.00000000"
    assert body[1]["initial_balance"] == "100.00000000"


def test_get_backtests_filters_by_strategy_id(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    btc_strategy = create_moving_average_strategy(db_session, symbol="BTCUSDT")
    eth_strategy = create_moving_average_strategy(db_session, symbol="ETHUSDT")
    add_candles(db_session, symbol="BTCUSDT", closes=["10", "10", "10", "20", "25"])
    add_candles(db_session, symbol="ETHUSDT", closes=["20", "20", "20", "30", "35"])

    with TestClient(app) as client:
        btc_response = client.post(
            "/api/v1/backtests",
            json={"strategy_id": btc_strategy.id, "initial_balance": "100", "source": "manual"},
        )
        eth_response = client.post(
            "/api/v1/backtests",
            json={"strategy_id": eth_strategy.id, "initial_balance": "100", "source": "manual"},
        )
        response = client.get(f"/api/v1/backtests?strategy_id={btc_strategy.id}")

    assert btc_response.status_code == 200
    assert eth_response.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["strategy_id"] == btc_strategy.id
    assert body[0]["symbol"] == "BTCUSDT"
