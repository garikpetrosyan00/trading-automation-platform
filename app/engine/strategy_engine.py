from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.engine.strategy_evaluator import StrategyEvaluator

ZERO = Decimal("0")
PRICE_THRESHOLD_STRATEGY_TYPE = "price_threshold"
MOVING_AVERAGE_CROSS_STRATEGY_TYPE = "moving_average_cross"
RSI_THRESHOLD_STRATEGY_TYPE = "rsi_threshold"
BOLLINGER_BANDS_STRATEGY_TYPE = "bollinger_bands"
DEFAULT_MOVING_AVERAGE_SHORT_WINDOW = 5
DEFAULT_MOVING_AVERAGE_LONG_WINDOW = 20
DEFAULT_RSI_PERIOD = 14
DEFAULT_RSI_OVERSOLD = Decimal("30")
DEFAULT_RSI_OVERBOUGHT = Decimal("70")
DEFAULT_BOLLINGER_PERIOD = 20
DEFAULT_BOLLINGER_STDDEV_MULTIPLIER = Decimal("2")


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
class RsiThresholdConfig:
    period: int | None
    oversold: Decimal | None
    overbought: Decimal | None
    order_quantity: Decimal | None
    invalid_parameter: str | None = None
    invalid_reason: str | None = None


@dataclass(frozen=True)
class BollingerBandsConfig:
    period: int | None
    stddev_multiplier: Decimal | None
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
        if strategy_type == RSI_THRESHOLD_STRATEGY_TYPE:
            return cls.evaluate_rsi_threshold(
                parameters=parameters,
                profile=profile,
                candles=candles or [],
                position_quantity=position_quantity,
            )
        if strategy_type == BOLLINGER_BANDS_STRATEGY_TYPE:
            return cls.evaluate_bollinger_bands(
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

    @classmethod
    def evaluate_rsi_threshold(
        cls,
        *,
        parameters: dict[str, Any] | None,
        profile,
        candles: list[Any],
        position_quantity: Decimal,
    ) -> StrategyDecision:
        config = cls.resolve_rsi_threshold_config(parameters, profile)
        if config.invalid_parameter is not None:
            return StrategyDecision(
                decision="skip",
                reason=config.invalid_reason or "invalid_strategy_parameter",
                metadata={
                    "event_decision": "skipped",
                    "parameter": config.invalid_parameter,
                    "strategy_type": RSI_THRESHOLD_STRATEGY_TYPE,
                },
            )

        assert config.period is not None
        assert config.oversold is not None
        assert config.overbought is not None
        required_candles = config.period + 1
        current_price = candles[-1].close_price if candles else None

        if len(candles) < required_candles:
            return cls._rsi_threshold_decision(
                decision="skip",
                event_decision="skipped",
                reason="insufficient_candles",
                current_price=current_price,
                position_quantity=position_quantity,
                period=config.period,
                oversold=config.oversold,
                overbought=config.overbought,
                candles_used=len(candles),
                order_quantity=config.order_quantity,
            )

        rsi = cls.relative_strength_index([candle.close_price for candle in candles[-required_candles:]])
        if position_quantity <= ZERO and rsi <= config.oversold:
            decision = "buy"
            event_decision = "buy"
            reason = "rsi is at or below oversold threshold"
        elif position_quantity > ZERO and rsi >= config.overbought:
            decision = "sell"
            event_decision = "sell"
            reason = "rsi is at or above overbought threshold"
        elif position_quantity <= ZERO:
            decision = "skip"
            event_decision = "skipped"
            reason = "rsi is above oversold threshold, so no buy signal"
        else:
            decision = "skip"
            event_decision = "skipped"
            reason = "rsi is below overbought threshold, so no sell signal"

        return cls._rsi_threshold_decision(
            decision=decision,
            event_decision=event_decision,
            reason=reason,
            current_price=current_price,
            position_quantity=position_quantity,
            period=config.period,
            oversold=config.oversold,
            overbought=config.overbought,
            candles_used=len(candles),
            rsi=rsi,
            order_quantity=config.order_quantity,
        )

    @classmethod
    def evaluate_bollinger_bands(
        cls,
        *,
        parameters: dict[str, Any] | None,
        profile,
        candles: list[Any],
        position_quantity: Decimal,
    ) -> StrategyDecision:
        config = cls.resolve_bollinger_bands_config(parameters, profile)
        if config.invalid_parameter is not None:
            return StrategyDecision(
                decision="skip",
                reason=config.invalid_reason or "invalid_strategy_parameter",
                metadata={
                    "event_decision": "skipped",
                    "parameter": config.invalid_parameter,
                    "strategy_type": BOLLINGER_BANDS_STRATEGY_TYPE,
                },
            )

        assert config.period is not None
        assert config.stddev_multiplier is not None
        current_price = candles[-1].close_price if candles else None

        if len(candles) < config.period:
            return cls._bollinger_bands_decision(
                decision="skip",
                event_decision="skipped",
                reason="insufficient_candles",
                current_price=current_price,
                position_quantity=position_quantity,
                period=config.period,
                stddev_multiplier=config.stddev_multiplier,
                candles_used=len(candles),
                order_quantity=config.order_quantity,
            )

        close_prices = [candle.close_price for candle in candles[-config.period :]]
        sma = cls.moving_average(close_prices)
        stddev = cls.standard_deviation(close_prices, sma=sma)
        upper_band = (sma + (config.stddev_multiplier * stddev)).quantize(Decimal("0.00000001"))
        lower_band = (sma - (config.stddev_multiplier * stddev)).quantize(Decimal("0.00000001"))

        if position_quantity <= ZERO and current_price <= lower_band:
            decision = "buy"
            event_decision = "buy"
            reason = "price is at or below lower bollinger band"
        elif position_quantity > ZERO and current_price >= upper_band:
            decision = "sell"
            event_decision = "sell"
            reason = "price is at or above upper bollinger band"
        elif position_quantity <= ZERO:
            decision = "skip"
            event_decision = "skipped"
            reason = "price is above lower bollinger band, so no buy signal"
        else:
            decision = "skip"
            event_decision = "skipped"
            reason = "price is below upper bollinger band, so no sell signal"

        return cls._bollinger_bands_decision(
            decision=decision,
            event_decision=event_decision,
            reason=reason,
            current_price=current_price,
            position_quantity=position_quantity,
            period=config.period,
            stddev_multiplier=config.stddev_multiplier,
            candles_used=len(candles),
            sma=sma,
            upper_band=upper_band,
            lower_band=lower_band,
            order_quantity=config.order_quantity,
        )

    @staticmethod
    def strategy_type(strategy) -> str:
        return getattr(strategy, "strategy_type", None) or PRICE_THRESHOLD_STRATEGY_TYPE

    @classmethod
    def required_candle_count(cls, *, strategy_type: str, parameters: dict[str, Any] | None) -> int | None:
        if strategy_type == MOVING_AVERAGE_CROSS_STRATEGY_TYPE:
            moving_average_config = cls.resolve_moving_average_cross_config(parameters)
            if moving_average_config.invalid_parameter is not None or moving_average_config.long_window is None:
                return None
            return moving_average_config.long_window + 1
        if strategy_type == RSI_THRESHOLD_STRATEGY_TYPE:
            rsi_config = cls.resolve_rsi_threshold_config(parameters)
            if rsi_config.invalid_parameter is not None or rsi_config.period is None:
                return None
            return rsi_config.period + 1
        if strategy_type == BOLLINGER_BANDS_STRATEGY_TYPE:
            bollinger_config = cls.resolve_bollinger_bands_config(parameters)
            if bollinger_config.invalid_parameter is not None or bollinger_config.period is None:
                return None
            return bollinger_config.period
        return None

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

    @classmethod
    def resolve_rsi_threshold_config(
        cls,
        parameters: dict[str, Any] | None,
        profile=None,
    ) -> RsiThresholdConfig:
        period, invalid_reason = cls.parse_integer_parameter(parameters, "period")
        if invalid_reason is not None:
            return RsiThresholdConfig(None, None, None, None, "period", invalid_reason)
        oversold, invalid_reason = cls.parse_decimal_parameter(parameters, "oversold")
        if invalid_reason is not None:
            return RsiThresholdConfig(None, None, None, None, "oversold", invalid_reason)
        overbought, invalid_reason = cls.parse_decimal_parameter(parameters, "overbought")
        if invalid_reason is not None:
            return RsiThresholdConfig(None, None, None, None, "overbought", invalid_reason)
        quantity, invalid_reason = cls.parse_decimal_parameter(parameters, "quantity")
        if invalid_reason is not None:
            return RsiThresholdConfig(None, None, None, None, "quantity", invalid_reason)

        period = period if period is not None else DEFAULT_RSI_PERIOD
        oversold = oversold if oversold is not None else DEFAULT_RSI_OVERSOLD
        overbought = overbought if overbought is not None else DEFAULT_RSI_OVERBOUGHT

        if oversold >= Decimal("100"):
            return RsiThresholdConfig(
                None,
                None,
                None,
                None,
                "oversold",
                "strategy parameter oversold must be less than 100",
            )
        if overbought >= Decimal("100"):
            return RsiThresholdConfig(
                None,
                None,
                None,
                None,
                "overbought",
                "strategy parameter overbought must be less than 100",
            )
        if oversold >= overbought:
            return RsiThresholdConfig(
                None,
                None,
                None,
                None,
                "oversold",
                "rsi_threshold oversold must be less than overbought",
            )

        if quantity is None and profile is not None:
            quantity = getattr(profile, "order_quantity", None)

        return RsiThresholdConfig(period, oversold, overbought, quantity)

    @classmethod
    def resolve_bollinger_bands_config(
        cls,
        parameters: dict[str, Any] | None,
        profile=None,
    ) -> BollingerBandsConfig:
        period, invalid_reason = cls.parse_integer_parameter(parameters, "period")
        if invalid_reason is not None:
            return BollingerBandsConfig(None, None, None, "period", invalid_reason)
        stddev_multiplier, invalid_reason = cls.parse_decimal_parameter(parameters, "stddev_multiplier")
        if invalid_reason is not None:
            return BollingerBandsConfig(None, None, None, "stddev_multiplier", invalid_reason)
        quantity, invalid_reason = cls.parse_decimal_parameter(parameters, "quantity")
        if invalid_reason is not None:
            return BollingerBandsConfig(None, None, None, "quantity", invalid_reason)

        period = period if period is not None else DEFAULT_BOLLINGER_PERIOD
        stddev_multiplier = (
            stddev_multiplier
            if stddev_multiplier is not None
            else DEFAULT_BOLLINGER_STDDEV_MULTIPLIER
        )

        if period < 2:
            return BollingerBandsConfig(
                None,
                None,
                None,
                "period",
                "bollinger_bands parameter period must be at least 2",
            )

        if quantity is None and profile is not None:
            quantity = getattr(profile, "order_quantity", None)

        return BollingerBandsConfig(period, stddev_multiplier, quantity)

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
    def relative_strength_index(values: list[Decimal]) -> Decimal:
        gains: list[Decimal] = []
        losses: list[Decimal] = []
        for previous, current in zip(values, values[1:]):
            change = current - previous
            gains.append(change if change > ZERO else ZERO)
            losses.append(abs(change) if change < ZERO else ZERO)

        average_gain = sum(gains, ZERO) / Decimal(len(gains))
        average_loss = sum(losses, ZERO) / Decimal(len(losses))
        if average_loss == ZERO and average_gain > ZERO:
            return Decimal("100.00000000")
        if average_gain == ZERO and average_loss > ZERO:
            return Decimal("0.00000000")
        if average_gain == ZERO and average_loss == ZERO:
            return Decimal("50.00000000")

        relative_strength = average_gain / average_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))
        return rsi.quantize(Decimal("0.00000001"))

    @staticmethod
    def standard_deviation(values: list[Decimal], *, sma: Decimal | None = None) -> Decimal:
        mean = sma if sma is not None else StrategyEngine.moving_average(values)
        variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values))
        return variance.sqrt().quantize(Decimal("0.00000001"))

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

    @staticmethod
    def _rsi_threshold_decision(
        *,
        decision: str,
        event_decision: str,
        reason: str,
        current_price: Decimal | None,
        position_quantity: Decimal,
        period: int,
        oversold: Decimal,
        overbought: Decimal,
        candles_used: int,
        rsi: Decimal | None = None,
        order_quantity: Decimal | None = None,
    ) -> StrategyDecision:
        metadata: dict[str, Any] = {
            "_order_quantity": order_quantity,
            "event_decision": event_decision,
            "position_qty": str(position_quantity),
            "period": period,
            "oversold": str(oversold),
            "overbought": str(overbought),
            "candles_used": candles_used,
            "strategy_type": RSI_THRESHOLD_STRATEGY_TYPE,
        }
        if rsi is not None:
            metadata["rsi"] = format(rsi, "f")
        return StrategyDecision(decision=decision, reason=reason, current_price=current_price, metadata=metadata)

    @staticmethod
    def _bollinger_bands_decision(
        *,
        decision: str,
        event_decision: str,
        reason: str,
        current_price: Decimal | None,
        position_quantity: Decimal,
        period: int,
        stddev_multiplier: Decimal,
        candles_used: int,
        sma: Decimal | None = None,
        upper_band: Decimal | None = None,
        lower_band: Decimal | None = None,
        order_quantity: Decimal | None = None,
    ) -> StrategyDecision:
        metadata: dict[str, Any] = {
            "_order_quantity": order_quantity,
            "event_decision": event_decision,
            "position_qty": str(position_quantity),
            "period": period,
            "stddev_multiplier": str(stddev_multiplier),
            "candles_used": candles_used,
            "strategy_type": BOLLINGER_BANDS_STRATEGY_TYPE,
        }
        if sma is not None:
            metadata["sma"] = format(sma, "f")
        if upper_band is not None:
            metadata["upper_band"] = format(upper_band, "f")
        if lower_band is not None:
            metadata["lower_band"] = format(lower_band, "f")
        return StrategyDecision(decision=decision, reason=reason, current_price=current_price, metadata=metadata)
