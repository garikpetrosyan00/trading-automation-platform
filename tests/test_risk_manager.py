from decimal import Decimal

from app.engine.risk import (
    RISK_REASON_ALLOWED,
    RISK_REASON_MAX_POSITION_QUANTITY_EXCEEDED,
    RISK_REASON_MAX_TRADE_QUANTITY_EXCEEDED,
    RISK_REASON_STOP_LOSS_TRIGGERED,
    RiskLimits,
    RiskManager,
)


def test_allows_buy_when_no_limits_are_configured() -> None:
    decision = RiskManager().evaluate(
        action="buy",
        quantity=Decimal("2"),
        current_position_quantity=Decimal("1"),
    )

    assert decision.allowed is True
    assert decision.action == "buy"
    assert decision.reason == RISK_REASON_ALLOWED


def test_blocks_buy_when_quantity_exceeds_max_trade_quantity() -> None:
    manager = RiskManager(RiskLimits(max_trade_quantity=Decimal("1")))

    decision = manager.evaluate(action="buy", quantity=Decimal("1.1"))

    assert decision.allowed is False
    assert decision.action == "skip"
    assert decision.reason == RISK_REASON_MAX_TRADE_QUANTITY_EXCEEDED


def test_blocks_sell_when_quantity_exceeds_max_trade_quantity() -> None:
    manager = RiskManager(RiskLimits(max_trade_quantity=Decimal("1")))

    decision = manager.evaluate(action="sell", quantity=Decimal("1.1"))

    assert decision.allowed is False
    assert decision.action == "skip"
    assert decision.reason == RISK_REASON_MAX_TRADE_QUANTITY_EXCEEDED


def test_blocks_buy_when_position_would_exceed_max_position_quantity() -> None:
    manager = RiskManager(RiskLimits(max_position_quantity=Decimal("5")))

    decision = manager.evaluate(
        action="buy",
        quantity=Decimal("2.1"),
        current_position_quantity=Decimal("3"),
    )

    assert decision.allowed is False
    assert decision.action == "skip"
    assert decision.reason == RISK_REASON_MAX_POSITION_QUANTITY_EXCEEDED


def test_allows_buy_when_position_would_equal_max_position_quantity() -> None:
    manager = RiskManager(RiskLimits(max_position_quantity=Decimal("5")))

    decision = manager.evaluate(
        action="buy",
        quantity=Decimal("2"),
        current_position_quantity=Decimal("3"),
    )

    assert decision.allowed is True
    assert decision.action == "buy"
    assert decision.reason == RISK_REASON_ALLOWED


def test_does_not_trigger_stop_loss_when_there_is_no_open_position() -> None:
    manager = RiskManager(RiskLimits(stop_loss_percent=Decimal("5")))

    decision = manager.evaluate(
        action="skip",
        current_position_quantity=Decimal("0"),
        entry_price=Decimal("100"),
        current_price=Decimal("95"),
    )

    assert decision.allowed is True
    assert decision.action == "skip"
    assert decision.reason == RISK_REASON_ALLOWED


def test_does_not_trigger_stop_loss_when_current_price_is_above_stop_level() -> None:
    manager = RiskManager(RiskLimits(stop_loss_percent=Decimal("5")))

    decision = manager.evaluate(
        action="skip",
        current_position_quantity=Decimal("1"),
        entry_price=Decimal("100"),
        current_price=Decimal("95.01"),
    )

    assert decision.allowed is True
    assert decision.action == "skip"
    assert decision.reason == RISK_REASON_ALLOWED


def test_triggers_stop_loss_when_current_price_reaches_stop_level() -> None:
    manager = RiskManager(RiskLimits(stop_loss_percent=Decimal("5")))

    decision = manager.evaluate(
        action="skip",
        current_position_quantity=Decimal("1"),
        entry_price=Decimal("100"),
        current_price=Decimal("95"),
    )

    assert decision.allowed is True
    assert decision.action == "sell"
    assert decision.reason == RISK_REASON_STOP_LOSS_TRIGGERED
    assert decision.details["stop_price"] == "95"


def test_triggers_stop_loss_when_current_price_goes_below_stop_level() -> None:
    manager = RiskManager(RiskLimits(stop_loss_percent=Decimal("5")))

    decision = manager.evaluate(
        action="skip",
        current_position_quantity=Decimal("1"),
        entry_price=Decimal("100"),
        current_price=Decimal("94.99"),
    )

    assert decision.allowed is True
    assert decision.action == "sell"
    assert decision.reason == RISK_REASON_STOP_LOSS_TRIGGERED


def test_handles_missing_entry_price_or_current_price_safely() -> None:
    manager = RiskManager(RiskLimits(stop_loss_percent=Decimal("5")))

    missing_entry_price = manager.evaluate(
        action="skip",
        current_position_quantity=Decimal("1"),
        entry_price=None,
        current_price=Decimal("95"),
    )
    missing_current_price = manager.evaluate(
        action="skip",
        current_position_quantity=Decimal("1"),
        entry_price=Decimal("100"),
        current_price=None,
    )

    assert missing_entry_price.allowed is True
    assert missing_entry_price.action == "skip"
    assert missing_entry_price.reason == RISK_REASON_ALLOWED
    assert missing_current_price.allowed is True
    assert missing_current_price.action == "skip"
    assert missing_current_price.reason == RISK_REASON_ALLOWED
