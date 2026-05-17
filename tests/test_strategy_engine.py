from decimal import Decimal
from types import SimpleNamespace

from app.engine.strategy_engine import StrategyEngine


def test_price_threshold_decides_buy_sell_and_skip() -> None:
    profile = SimpleNamespace(
        entry_below=Decimal("100"),
        exit_above=Decimal("110"),
        order_quantity=Decimal("0.1"),
    )

    buy_decision = StrategyEngine.evaluate(
        strategy_type="price_threshold",
        parameters={},
        profile=profile,
        latest_price=Decimal("99"),
        position_quantity=Decimal("0"),
    )
    sell_decision = StrategyEngine.evaluate(
        strategy_type="price_threshold",
        parameters={},
        profile=profile,
        latest_price=Decimal("111"),
        position_quantity=Decimal("0.1"),
    )
    skip_decision = StrategyEngine.evaluate(
        strategy_type="price_threshold",
        parameters={},
        profile=profile,
        latest_price=None,
        position_quantity=Decimal("0"),
    )

    assert buy_decision.decision == "buy"
    assert buy_decision.reason == "price is below strategy buy_below"
    assert sell_decision.decision == "sell"
    assert sell_decision.reason == "price is above strategy sell_above and position exists"
    assert skip_decision.decision == "skip"
    assert skip_decision.reason == "no_latest_price"


def test_unsupported_strategy_type_skips_safely() -> None:
    decision = StrategyEngine.evaluate(
        strategy_type="rsi",
        parameters={},
        profile=SimpleNamespace(),
        latest_price=Decimal("100"),
        position_quantity=Decimal("0"),
    )

    assert decision.decision == "skip"
    assert decision.reason == "unsupported strategy type: rsi"
    assert decision.event_payload()["decision"] == "skipped"


def test_moving_average_cross_with_insufficient_data_skips_safely() -> None:
    candles = [
        SimpleNamespace(close_price=Decimal("10")),
        SimpleNamespace(close_price=Decimal("11")),
    ]

    decision = StrategyEngine.evaluate(
        strategy_type="moving_average_cross",
        parameters={"short_window": "2", "long_window": "3", "quantity": "0.1"},
        profile=SimpleNamespace(),
        latest_price=Decimal("11"),
        position_quantity=Decimal("0"),
        candles=candles,
    )

    assert decision.decision == "skip"
    assert decision.reason == "insufficient_candles"
    assert decision.current_price == Decimal("11")
    assert decision.metadata["candles_used"] == 2


def test_moving_average_cross_with_no_crossover_skips_with_metadata() -> None:
    candles = [
        SimpleNamespace(close_price=Decimal("10")),
        SimpleNamespace(close_price=Decimal("11")),
        SimpleNamespace(close_price=Decimal("12")),
        SimpleNamespace(close_price=Decimal("13")),
    ]

    decision = StrategyEngine.evaluate(
        strategy_type="moving_average_cross",
        parameters={"short_window": "2", "long_window": "3", "quantity": "0.1"},
        profile=SimpleNamespace(),
        latest_price=Decimal("13"),
        position_quantity=Decimal("0"),
        candles=candles,
    )

    assert decision.decision == "skip"
    assert decision.reason == "moving averages did not cross bullish, so no buy signal"
    assert decision.event_payload()["decision"] == "skipped"
    assert decision.metadata["previous_short_ma"] == "11.50000000"
    assert decision.metadata["current_short_ma"] == "12.50000000"


def test_moving_average_cross_bullish_crossover_buys() -> None:
    candles = [
        SimpleNamespace(close_price=Decimal("10")),
        SimpleNamespace(close_price=Decimal("10")),
        SimpleNamespace(close_price=Decimal("10")),
        SimpleNamespace(close_price=Decimal("20")),
    ]

    decision = StrategyEngine.evaluate(
        strategy_type="moving_average_cross",
        parameters={"short_window": "2", "long_window": "3", "quantity": "0.1"},
        profile=SimpleNamespace(),
        latest_price=Decimal("20"),
        position_quantity=Decimal("0"),
        candles=candles,
    )

    assert decision.decision == "buy"
    assert decision.reason == "short moving average crossed above long moving average"
    assert decision.metadata["_order_quantity"] == Decimal("0.1")


def test_moving_average_cross_uses_default_windows_and_profile_quantity() -> None:
    candles = [SimpleNamespace(close_price=Decimal("10")) for _ in range(20)]
    candles.append(SimpleNamespace(close_price=Decimal("100")))
    profile = SimpleNamespace(order_quantity=Decimal("0.25"))

    decision = StrategyEngine.evaluate(
        strategy_type="moving_average_cross",
        parameters={},
        profile=profile,
        latest_price=Decimal("100"),
        position_quantity=Decimal("0"),
        candles=candles,
    )

    assert decision.decision == "buy"
    assert decision.metadata["short_window"] == 5
    assert decision.metadata["long_window"] == 20
    assert decision.metadata["_order_quantity"] == Decimal("0.25")


def test_moving_average_cross_bearish_crossover_sells() -> None:
    candles = [
        SimpleNamespace(close_price=Decimal("20")),
        SimpleNamespace(close_price=Decimal("20")),
        SimpleNamespace(close_price=Decimal("20")),
        SimpleNamespace(close_price=Decimal("10")),
    ]

    decision = StrategyEngine.evaluate(
        strategy_type="moving_average_cross",
        parameters={"short_window": "2", "long_window": "3", "quantity": "0.1"},
        profile=SimpleNamespace(),
        latest_price=Decimal("10"),
        position_quantity=Decimal("0.1"),
        candles=candles,
    )

    assert decision.decision == "sell"
    assert decision.reason == "short moving average crossed below long moving average"
    assert decision.metadata["_order_quantity"] == Decimal("0.1")


def test_rsi_threshold_buys_sells_and_holds_with_metadata() -> None:
    profile = SimpleNamespace(order_quantity=Decimal("0.1"))
    buy_candles = [SimpleNamespace(close_price=Decimal(value)) for value in ("10", "9", "8", "7")]
    sell_candles = [SimpleNamespace(close_price=Decimal(value)) for value in ("7", "8", "9", "10")]
    hold_candles = [SimpleNamespace(close_price=Decimal(value)) for value in ("10", "11", "10", "11")]

    buy_decision = StrategyEngine.evaluate(
        strategy_type="rsi_threshold",
        parameters={"period": "3", "oversold": "30", "overbought": "70", "quantity": "0.2"},
        profile=profile,
        latest_price=Decimal("7"),
        position_quantity=Decimal("0"),
        candles=buy_candles,
    )
    sell_decision = StrategyEngine.evaluate(
        strategy_type="rsi_threshold",
        parameters={"period": "3", "oversold": "30", "overbought": "70", "quantity": "0.2"},
        profile=profile,
        latest_price=Decimal("10"),
        position_quantity=Decimal("0.2"),
        candles=sell_candles,
    )
    hold_decision = StrategyEngine.evaluate(
        strategy_type="rsi_threshold",
        parameters={"period": "3", "oversold": "30", "overbought": "70", "quantity": "0.2"},
        profile=profile,
        latest_price=Decimal("11"),
        position_quantity=Decimal("0"),
        candles=hold_candles,
    )

    assert buy_decision.decision == "buy"
    assert buy_decision.reason == "rsi is at or below oversold threshold"
    assert buy_decision.metadata["rsi"] == "0.00000000"
    assert buy_decision.metadata["period"] == 3
    assert buy_decision.metadata["oversold"] == "30"
    assert buy_decision.metadata["overbought"] == "70"
    assert buy_decision.metadata["position_qty"] == "0"
    assert buy_decision.metadata["_order_quantity"] == Decimal("0.2")
    assert sell_decision.decision == "sell"
    assert sell_decision.reason == "rsi is at or above overbought threshold"
    assert sell_decision.metadata["rsi"] == "100.00000000"
    assert hold_decision.decision == "skip"
    assert hold_decision.reason == "rsi is above oversold threshold, so no buy signal"
    assert hold_decision.metadata["rsi"] == "66.66666667"


def test_rsi_threshold_with_insufficient_data_skips_safely() -> None:
    candles = [
        SimpleNamespace(close_price=Decimal("10")),
        SimpleNamespace(close_price=Decimal("9")),
        SimpleNamespace(close_price=Decimal("8")),
    ]

    decision = StrategyEngine.evaluate(
        strategy_type="rsi_threshold",
        parameters={"period": "3", "oversold": "30", "overbought": "70", "quantity": "0.2"},
        profile=SimpleNamespace(order_quantity=Decimal("0.1")),
        latest_price=Decimal("8"),
        position_quantity=Decimal("0"),
        candles=candles,
    )

    assert decision.decision == "skip"
    assert decision.reason == "insufficient_candles"
    assert decision.current_price == Decimal("8")
    assert decision.metadata["candles_used"] == 3
    assert decision.metadata["period"] == 3
    assert "rsi" not in decision.metadata


def test_bollinger_bands_buys_sells_and_holds_with_metadata() -> None:
    profile = SimpleNamespace(order_quantity=Decimal("0.1"))
    buy_candles = [SimpleNamespace(close_price=Decimal(value)) for value in ("10", "10", "1")]
    sell_candles = [SimpleNamespace(close_price=Decimal(value)) for value in ("1", "1", "10")]
    hold_candles = [SimpleNamespace(close_price=Decimal(value)) for value in ("9", "10", "11")]

    buy_decision = StrategyEngine.evaluate(
        strategy_type="bollinger_bands",
        parameters={"period": "3", "stddev_multiplier": "0.5", "quantity": "0.2"},
        profile=profile,
        latest_price=Decimal("1"),
        position_quantity=Decimal("0"),
        candles=buy_candles,
    )
    sell_decision = StrategyEngine.evaluate(
        strategy_type="bollinger_bands",
        parameters={"period": "3", "stddev_multiplier": "0.5", "quantity": "0.2"},
        profile=profile,
        latest_price=Decimal("10"),
        position_quantity=Decimal("0.2"),
        candles=sell_candles,
    )
    hold_decision = StrategyEngine.evaluate(
        strategy_type="bollinger_bands",
        parameters={"period": "3", "stddev_multiplier": "2", "quantity": "0.2"},
        profile=profile,
        latest_price=Decimal("11"),
        position_quantity=Decimal("0"),
        candles=hold_candles,
    )

    assert buy_decision.decision == "buy"
    assert buy_decision.reason == "price is at or below lower bollinger band"
    assert buy_decision.metadata["sma"] == "7.00000000"
    assert buy_decision.metadata["upper_band"] == "9.12132034"
    assert buy_decision.metadata["lower_band"] == "4.87867966"
    assert buy_decision.metadata["period"] == 3
    assert buy_decision.metadata["stddev_multiplier"] == "0.5"
    assert buy_decision.metadata["position_qty"] == "0"
    assert buy_decision.metadata["_order_quantity"] == Decimal("0.2")
    assert sell_decision.decision == "sell"
    assert sell_decision.reason == "price is at or above upper bollinger band"
    assert hold_decision.decision == "skip"
    assert hold_decision.reason == "price is above lower bollinger band, so no buy signal"


def test_bollinger_bands_with_insufficient_data_skips_safely() -> None:
    candles = [
        SimpleNamespace(close_price=Decimal("10")),
        SimpleNamespace(close_price=Decimal("9")),
    ]

    decision = StrategyEngine.evaluate(
        strategy_type="bollinger_bands",
        parameters={"period": "3", "stddev_multiplier": "2", "quantity": "0.2"},
        profile=SimpleNamespace(order_quantity=Decimal("0.1")),
        latest_price=Decimal("9"),
        position_quantity=Decimal("0"),
        candles=candles,
    )

    assert decision.decision == "skip"
    assert decision.reason == "insufficient_candles"
    assert decision.current_price == Decimal("9")
    assert decision.metadata["candles_used"] == 2
    assert decision.metadata["period"] == 3
    assert "sma" not in decision.metadata


def test_price_threshold_does_not_require_candles() -> None:
    profile = SimpleNamespace(
        entry_below=Decimal("100"),
        exit_above=Decimal("110"),
        order_quantity=Decimal("0.1"),
    )

    decision = StrategyEngine.evaluate(
        strategy_type="price_threshold",
        parameters={},
        profile=profile,
        latest_price=Decimal("99"),
        position_quantity=Decimal("0"),
        candles=None,
    )

    assert decision.decision == "buy"
