from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.engine.strategy_evaluator import StrategyEvaluator

ZERO = Decimal("0")
PRICE_THRESHOLD_STRATEGY_TYPE = "price_threshold"
MOVING_AVERAGE_CROSS_STRATEGY_TYPE = "moving_average_cross"
DEFAULT_MOVING_AVERAGE_SHORT_WINDOW = 5
DEFAULT_MOVING_AVERAGE_LONG_WINDOW = 20


@dataclass(frozen=True)
class PriceThresholdConfig:
    entry_below: Decimal | None
    exit_above: Decimal | None
    order_quantity: Decimal | None
    invalid_parameter: str | None = None
    invalid_reason: str | None = None


@dataclass(frozen=True)
class MovingAverageCrossConfig:
    short_window: int | None
    long_window: int | None
    order_quantity: Decimal | None
    invalid_parameter: str | None = None
    invalid_reason: str | None = None


@dataclass(frozen=True)
class StrategyDecision:
    decision: str
    reason: str
    current_price: Decimal | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> str:
        return self.decision

    def event_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision": self.metadata.get("event_decision", self.decision),
            "reason": self.reason,
            "detail": self.reason,
            **{
                key: value
                for key, value in self.metadata.items()
                if not key.startswith("_") and key != "event_decision"
            },
        }
        if self.current_price is not None:
            payload["current_price"] = str(self.current_price)
        return payload


class StrategyEngine:
    @classmethod
    def evaluate(
        cls,
        *,
        strategy_type: str,
        parameters: dict[str, Any] | None,
        profile,
        latest_price: Decimal | None,
        position_quantity: Decimal,
        candles: list[Any] | None = None,
    ) -> StrategyDecision:
        if strategy_type == PRICE_THRESHOLD_STRATEGY_TYPE:
            return cls.evaluate_price_threshold(
                parameters=parameters,
                profile=profile,
                latest_price=latest_price,
                position_quantity=position_quantity,
            )
        if strategy_type == MOVING_AVERAGE_CROSS_STRATEGY_TYPE:
            return cls.evaluate_moving_average_cross(
                parameters=parameters,
                profile=profile,
                candles=candles or [],
                position_quantity=position_quantity,
            )
        return StrategyDecision(
            decision="skip",
            reason=f"unsupported strategy type: {strategy_type}",
            metadata={
                "event_decision": "skipped",
                "strategy_type": strategy_type,
            },
        )

    @classmethod
    def evaluate_price_threshold(
        cls,
        *,
        parameters: dict[str, Any] | None,
        profile,
        latest_price: Decimal | None,
        position_quantity: Decimal,
    ) -> StrategyDecision:
        config = cls.resolve_price_threshold_config(parameters, profile)
        if config.invalid_parameter is not None:
            return StrategyDecision(
                decision="skip",
                reason="invalid_strategy_parameter",
                metadata={
                    "event_decision": "skipped",
                    "detail": config.invalid_reason,
                    "parameter": config.invalid_parameter,
                },
            )

        evaluation = StrategyEvaluator.evaluate_price_threshold(
            latest_price=latest_price,
            position_quantity=position_quantity,
            entry_below=config.entry_below,
            exit_above=config.exit_above,
        )
        detail = cls.price_threshold_decision_detail(
            evaluation.reason,
            entry_below=config.entry_below,
            exit_above=config.exit_above,
        )
        return StrategyDecision(
            decision=evaluation.action,
            reason=detail,
            current_price=latest_price,
            metadata={
                "_raw_reason": evaluation.reason,
                "_order_quantity": config.order_quantity,
                "event_decision": evaluation.action,
                "position_qty": str(position_quantity),
                **({"buy_below": str(config.entry_below)} if config.entry_below is not None else {}),
                **({"sell_above": str(config.exit_above)} if config.exit_above is not None else {}),
            },
        )

    @classmethod
    def evaluate_moving_average_cross(
        cls,
        *,
        parameters: dict[str, Any] | None,
        profile,
        candles: list[Any],
        position_quantity: Decimal,
    ) -> StrategyDecision:
        config = cls.resolve_moving_average_cross_config(parameters, profile)
        if config.invalid_parameter is not None:
            return StrategyDecision(
                decision="skip",
                reason=config.invalid_reason or "invalid_strategy_parameter",
                metadata={
                    "event_decision": "skipped",
                    "parameter": config.invalid_parameter,
                    "strategy_type": MOVING_AVERAGE_CROSS_STRATEGY_TYPE,
                },
            )

        assert config.short_window is not None
        assert config.long_window is not None
        required_candles = config.long_window + 1

        if len(candles) < required_candles:
            return cls._moving_average_decision(
                decision="skip",
                event_decision="skipped",
                reason="insufficient_candles",
                current_price=candles[-1].close_price if candles else None,
                position_quantity=position_quantity,
                short_window=config.short_window,
                long_window=config.long_window,
                candles_used=len(candles),
            )

        previous_window = candles[-required_candles:-1]
        current_window = candles[-config.long_window :]
        previous_short_ma = cls.moving_average([candle.close_price for candle in previous_window[-config.short_window :]])
        previous_long_ma = cls.moving_average([candle.close_price for candle in previous_window])
        current_short_ma = cls.moving_average([candle.close_price for candle in current_window[-config.short_window :]])
        current_long_ma = cls.moving_average([candle.close_price for candle in current_window])
        current_price = candles[-1].close_price

        if (
            position_quantity <= ZERO
            and previous_short_ma <= previous_long_ma
            and current_short_ma > current_long_ma
        ):
            decision = "buy"
            event_decision = "buy"
            reason = "short moving average crossed above long moving average"
        elif (
            position_quantity > ZERO
            and previous_short_ma >= previous_long_ma
            and current_short_ma < current_long_ma
        ):
            decision = "sell"
            event_decision = "sell"
            reason = "short moving average crossed below long moving average"
        elif position_quantity <= ZERO:
            decision = "skip"
            event_decision = "skipped"
            reason = "moving averages did not cross bullish, so no buy signal"
        else:
            decision = "skip"
            event_decision = "skipped"
            reason = "moving averages did not cross bearish, so no sell signal"

        return cls._moving_average_decision(
            decision=decision,
            event_decision=event_decision,
            reason=reason,
            current_price=current_price,
            position_quantity=position_quantity,
            short_window=config.short_window,
            long_window=config.long_window,
            previous_short_ma=previous_short_ma,
            previous_long_ma=previous_long_ma,
            current_short_ma=current_short_ma,
            current_long_ma=current_long_ma,
            candles_used=len(candles),
            order_quantity=config.order_quantity,
        )

    @staticmethod
    def strategy_type(strategy) -> str:
        return getattr(strategy, "strategy_type", None) or PRICE_THRESHOLD_STRATEGY_TYPE

    @classmethod
    def required_candle_count(cls, *, strategy_type: str, parameters: dict[str, Any] | None) -> int | None:
        if strategy_type != MOVING_AVERAGE_CROSS_STRATEGY_TYPE:
            return None
        config = cls.resolve_moving_average_cross_config(parameters)
        if config.invalid_parameter is not None or config.long_window is None:
            return None
        return config.long_window + 1

    @classmethod
    def resolve_price_threshold_config(cls, parameters: dict[str, Any] | None, profile) -> PriceThresholdConfig:
        parsed_parameters: dict[str, Decimal | None] = {}
        for key in ("buy_below", "sell_above", "quantity"):
            value, invalid_reason = cls.parse_decimal_parameter(parameters, key)
            if invalid_reason is not None:
                return PriceThresholdConfig(None, None, None, key, invalid_reason)
            parsed_parameters[key] = value

        return PriceThresholdConfig(
            entry_below=parsed_parameters["buy_below"] if parsed_parameters["buy_below"] is not None else profile.entry_below,
            exit_above=parsed_parameters["sell_above"] if parsed_parameters["sell_above"] is not None else profile.exit_above,
            order_quantity=parsed_parameters["quantity"] if parsed_parameters["quantity"] is not None else profile.order_quantity,
        )

    @classmethod
    def resolve_moving_average_cross_config(
        cls,
        parameters: dict[str, Any] | None,
        profile=None,
    ) -> MovingAverageCrossConfig:
        short_window, invalid_reason = cls.parse_integer_parameter(parameters, "short_window")
        if invalid_reason is not None:
            return MovingAverageCrossConfig(None, None, None, "short_window", invalid_reason)
        long_window, invalid_reason = cls.parse_integer_parameter(parameters, "long_window")
        if invalid_reason is not None:
            return MovingAverageCrossConfig(None, None, None, "long_window", invalid_reason)
        quantity, invalid_reason = cls.parse_decimal_parameter(parameters, "quantity")
        if invalid_reason is not None:
            return MovingAverageCrossConfig(None, None, None, "quantity", invalid_reason)

        if short_window is None:
            short_window = DEFAULT_MOVING_AVERAGE_SHORT_WINDOW
        if long_window is None:
            long_window = DEFAULT_MOVING_AVERAGE_LONG_WINDOW
        if short_window >= long_window:
            return MovingAverageCrossConfig(
                None,
                None,
                None,
                "short_window",
                "strategy parameter short_window must be less than long_window",
            )

        if quantity is None and profile is not None:
            quantity = getattr(profile, "order_quantity", None)

        return MovingAverageCrossConfig(short_window, long_window, quantity)

    @staticmethod
    def parse_decimal_parameter(parameters: dict[str, Any] | None, key: str) -> tuple[Decimal | None, str | None]:
        if not parameters or key not in parameters:
            return None, None

        raw_value = parameters[key]
        if raw_value is None or raw_value == "":
            return None, None

        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, ValueError):
            return None, f"strategy parameter {key} must be a positive number"

        if not value.is_finite() or value <= ZERO:
            return None, f"strategy parameter {key} must be a positive number"

        return value, None

    @classmethod
    def parse_integer_parameter(cls, parameters: dict[str, Any] | None, key: str) -> tuple[int | None, str | None]:
        value, invalid_reason = cls.parse_decimal_parameter(parameters, key)
        if invalid_reason is not None or value is None:
            return None, invalid_reason
        if value != value.to_integral_value():
            return None, f"strategy parameter {key} must be a positive integer"
        return int(value), None

    @staticmethod
    def moving_average(values: list[Decimal]) -> Decimal:
        return (sum(values, ZERO) / Decimal(len(values))).quantize(Decimal("0.00000001"))

    @staticmethod
    def price_threshold_decision_detail(
        reason: str,
        *,
        entry_below: Decimal | None,
        exit_above: Decimal | None,
    ) -> str:
        if reason == "entry_threshold_reached":
            return "price is below strategy buy_below"
        if reason == "entry_threshold_not_met":
            return "price did not go below buy_below, so no buy signal"
        if reason == "exit_threshold_reached":
            return "price is above strategy sell_above and position exists"
        if reason == "exit_threshold_not_met":
            return "price did not go above sell_above, so no sell signal"
        if reason == "entry_below_not_configured" and entry_below is None:
            return "strategy buy_below is missing and execution profile entry_below is not configured"
        if reason == "exit_above_not_configured" and exit_above is None:
            return "strategy sell_above is missing and execution profile exit_above is not configured"
        return reason

    @staticmethod
    def _moving_average_decision(
        *,
        decision: str,
        event_decision: str,
        reason: str,
        current_price: Decimal | None,
        position_quantity: Decimal,
        short_window: int,
        long_window: int,
        previous_short_ma: Decimal | None = None,
        previous_long_ma: Decimal | None = None,
        current_short_ma: Decimal | None = None,
        current_long_ma: Decimal | None = None,
        candles_used: int,
        order_quantity: Decimal | None = None,
    ) -> StrategyDecision:
        metadata: dict[str, Any] = {
            "_order_quantity": order_quantity,
            "event_decision": event_decision,
            "position_qty": str(position_quantity),
            "short_window": short_window,
            "long_window": long_window,
            "candles_used": candles_used,
            "strategy_type": MOVING_AVERAGE_CROSS_STRATEGY_TYPE,
        }
        if previous_short_ma is not None:
            metadata["previous_short_ma"] = str(previous_short_ma)
        if previous_long_ma is not None:
            metadata["previous_long_ma"] = str(previous_long_ma)
        if current_short_ma is not None:
            metadata["current_short_ma"] = str(current_short_ma)
        if current_long_ma is not None:
            metadata["current_long_ma"] = str(current_long_ma)
        return StrategyDecision(decision=decision, reason=reason, current_price=current_price, metadata=metadata)
