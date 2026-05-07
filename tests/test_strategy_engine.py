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
