from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.engine.backtesting import BacktestingEngine
from app.engine.strategy_engine import StrategyEngine
from app.models.market_candle import MarketCandle
from app.repositories.market_candle import MarketCandleRepository


def add_candles(
    session,
    *,
    symbol: str = "BTCUSDT",
    timeframe: str = "1m",
    closes: list[str],
    source: str = "manual",
) -> None:
    start = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)
    for index, close in enumerate(closes):
        close_price = Decimal(close)
        open_time = start + timedelta(minutes=index)
        session.add(
            MarketCandle(
                symbol=symbol,
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


def moving_average_strategy(**parameter_overrides):
    parameters = {
        "short_window": "2",
        "long_window": "3",
        "quantity": "1",
    }
    parameters.update(parameter_overrides)
    return SimpleNamespace(
        symbol="BTCUSDT",
        timeframe="1m",
        strategy_type="moving_average_cross",
        parameters=parameters,
    )


def price_threshold_strategy(**parameter_overrides):
    parameters = {
        "buy_below": "11",
        "sell_above": "19",
        "quantity": "1",
    }
    parameters.update(parameter_overrides)
    return SimpleNamespace(
        symbol="BTCUSDT",
        timeframe="1m",
        strategy_type="price_threshold",
        parameters=parameters,
    )


def run_backtest(db_session, strategy, *, initial_balance: str = "100"):
    return BacktestingEngine(MarketCandleRepository(db_session)).run(
        strategy=strategy,
        initial_balance=Decimal(initial_balance),
    )


def test_backtest_insufficient_candles_returns_safe_no_trade_result(db_session) -> None:
    add_candles(db_session, closes=["10", "10", "20"])

    result = run_backtest(db_session, moving_average_strategy())

    assert result.number_of_trades == 0
    assert result.closed_trades == 0
    assert result.open_position is False
    assert result.cash_balance == Decimal("100")
    assert result.position_quantity == Decimal("0")
    assert result.final_balance == Decimal("100")
    assert result.realized_pnl == Decimal("0")
    assert result.unrealized_pnl == Decimal("0")
    assert all(decision.decision == "skip" for decision in result.decisions)


def test_backtest_bullish_crossover_opens_position(db_session) -> None:
    add_candles(db_session, closes=["10", "10", "10", "20"])

    result = run_backtest(db_session, moving_average_strategy())

    assert result.number_of_trades == 1
    assert result.closed_trades == 0
    assert result.open_position is True
    assert len(result.trades) == result.number_of_trades
    assert result.trades[0].side == "buy"
    assert result.trades[0].price == Decimal("20.00000000")
    assert result.position_quantity == Decimal("1")
    assert result.entry_price == Decimal("20.00000000")
    assert result.cash_balance == Decimal("80.00000000")
    assert result.final_balance == Decimal("100.00000000")


def test_backtest_no_crossover_returns_no_trade_result(db_session) -> None:
    add_candles(db_session, closes=["10", "11", "12", "13"])

    result = run_backtest(db_session, moving_average_strategy())

    assert result.number_of_trades == 0
    assert result.closed_trades == 0
    assert result.open_position is False
    assert result.cash_balance == Decimal("100")
    assert result.position_quantity == Decimal("0")
    assert result.final_balance == Decimal("100.00000000")
    assert result.decisions[-1].decision == "skip"
    assert result.decisions[-1].reason == "moving averages did not cross bullish, so no buy signal"


def test_backtest_bearish_crossover_closes_position(db_session) -> None:
    add_candles(db_session, closes=["10", "10", "10", "20", "20", "20", "20", "10"])

    result = run_backtest(db_session, moving_average_strategy())

    assert result.number_of_trades == 2
    assert result.closed_trades == 1
    assert result.open_position is False
    assert len(result.trades) == result.number_of_trades
    assert [trade.side for trade in result.trades] == ["buy", "sell"]
    assert result.trades[1].realized_pnl == Decimal("-10.00000000")
    assert result.position_quantity == Decimal("0")
    assert result.entry_price is None
    assert result.cash_balance == Decimal("90.00000000")
    assert result.realized_pnl == Decimal("-10.00000000")
    assert result.losing_trades == 1
    assert result.winning_trades == 0


def test_backtest_invalid_moving_average_parameters_return_safe_no_trade_result(db_session) -> None:
    add_candles(db_session, closes=["10", "10", "10", "20"])

    result = run_backtest(db_session, moving_average_strategy(short_window="3", long_window="3"))

    assert result.number_of_trades == 0
    assert result.closed_trades == 0
    assert result.open_position is False
    assert result.cash_balance == Decimal("100")
    assert result.position_quantity == Decimal("0")
    assert result.final_balance == Decimal("100.00000000")
    assert all(decision.decision == "skip" for decision in result.decisions)
    assert all(decision.reason == "strategy parameter short_window must be less than long_window" for decision in result.decisions)
    assert all(decision.metadata["parameter"] == "short_window" for decision in result.decisions)


def test_backtest_moving_average_cross_uses_default_windows(db_session) -> None:
    add_candles(db_session, closes=["10"] * 20 + ["100"])

    result = run_backtest(db_session, moving_average_strategy(short_window=None, long_window=None))

    assert result.number_of_trades == 1
    assert result.trades[0].side == "buy"
    assert result.trades[0].price == Decimal("100.00000000")
    assert result.decisions[-1].metadata["short_window"] == 5
    assert result.decisions[-1].metadata["long_window"] == 20


def test_backtest_final_balance_includes_open_position_marked_to_last_close(db_session) -> None:
    add_candles(db_session, closes=["10", "10", "10", "20", "25"])

    result = run_backtest(db_session, moving_average_strategy())

    assert result.cash_balance == Decimal("80.00000000")
    assert result.position_quantity == Decimal("1")
    assert result.open_position is True
    assert result.number_of_trades == 1
    assert result.closed_trades == 0
    assert len(result.trades) == result.number_of_trades
    assert result.realized_pnl == Decimal("0")
    assert result.unrealized_pnl == Decimal("5.00000000")
    assert result.final_balance == Decimal("105.00000000")


def test_backtest_does_not_look_ahead_when_evaluating_each_candle(db_session, monkeypatch) -> None:
    add_candles(db_session, closes=["10", "10", "10", "20", "25"])
    original_evaluate = StrategyEngine.evaluate
    seen_lengths: list[int] = []
    seen_last_prices: list[Decimal] = []

    def spy_evaluate(**kwargs):
        candles = kwargs["candles"]
        seen_lengths.append(len(candles))
        seen_last_prices.append(candles[-1].close_price)
        return original_evaluate(**kwargs)

    monkeypatch.setattr(StrategyEngine, "evaluate", spy_evaluate)

    result = run_backtest(db_session, moving_average_strategy())

    assert result.candles_processed == 5
    assert seen_lengths == [1, 2, 3, 4, 5]
    assert seen_last_prices == [
        Decimal("10.00000000"),
        Decimal("10.00000000"),
        Decimal("10.00000000"),
        Decimal("20.00000000"),
        Decimal("25.00000000"),
    ]


def test_backtest_uses_configured_candle_source(db_session) -> None:
    add_candles(db_session, closes=["10", "11", "12", "13"], source="manual")
    add_candles(db_session, closes=["10", "10", "10", "20"], source="binance")

    result = run_backtest(db_session, moving_average_strategy(candle_source="binance"))

    assert result.source == "binance"
    assert result.number_of_trades == 1
    assert result.open_position is True
    assert result.trades[0].side == "buy"
    assert result.trades[0].price == Decimal("20.00000000")


def test_backtest_price_threshold_behavior_is_preserved(db_session) -> None:
    add_candles(db_session, closes=["10", "20"])

    result = run_backtest(db_session, price_threshold_strategy())

    assert result.number_of_trades == 2
    assert result.closed_trades == 1
    assert [trade.side for trade in result.trades] == ["buy", "sell"]
    assert result.trades[0].price == Decimal("10.00000000")
    assert result.trades[1].price == Decimal("20.00000000")
    assert result.cash_balance == Decimal("110.00000000")
    assert result.realized_pnl == Decimal("10.00000000")
    assert result.final_balance == Decimal("110.00000000")
