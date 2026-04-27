from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
StrategyType = Literal["price_threshold", "moving_average_cross"]
PRICE_THRESHOLD_PARAMETER_KEYS = ("buy_below", "sell_above", "quantity")
MOVING_AVERAGE_CROSS_PARAMETER_KEYS = ("short_window", "long_window", "quantity")


def validate_price_threshold_parameters(parameters: dict[str, Any] | None) -> dict[str, Any] | None:
    if not parameters:
        return parameters

    missing_keys = [key for key in PRICE_THRESHOLD_PARAMETER_KEYS if key not in parameters]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"price_threshold parameters are missing required keys: {missing}")

    parsed_values: dict[str, Decimal] = {}
    for key in PRICE_THRESHOLD_PARAMETER_KEYS:
        try:
            value = Decimal(str(parameters[key]))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"price_threshold parameter {key} must be a positive number") from exc

        if not value.is_finite() or value <= Decimal("0"):
            raise ValueError(f"price_threshold parameter {key} must be a positive number")
        parsed_values[key] = value

    if parsed_values["buy_below"] >= parsed_values["sell_above"]:
        raise ValueError("price_threshold buy_below must be less than sell_above")

    return parameters


def _parse_positive_number(strategy_type: str, key: str, value: Any) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{strategy_type} parameter {key} must be a positive number") from exc

    if not parsed.is_finite() or parsed <= Decimal("0"):
        raise ValueError(f"{strategy_type} parameter {key} must be a positive number")
    return parsed


def _parse_positive_integer(strategy_type: str, key: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{strategy_type} parameter {key} must be a positive integer")

    parsed = _parse_positive_number(strategy_type, key, value)
    if parsed != parsed.to_integral_value():
        raise ValueError(f"{strategy_type} parameter {key} must be a positive integer")
    return int(parsed)


def validate_moving_average_cross_parameters(parameters: dict[str, Any] | None) -> dict[str, Any] | None:
    if not parameters:
        return parameters

    missing_keys = [key for key in MOVING_AVERAGE_CROSS_PARAMETER_KEYS if key not in parameters]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"moving_average_cross parameters are missing required keys: {missing}")

    short_window = _parse_positive_integer(
        "moving_average_cross",
        "short_window",
        parameters["short_window"],
    )
    long_window = _parse_positive_integer(
        "moving_average_cross",
        "long_window",
        parameters["long_window"],
    )
    _parse_positive_number("moving_average_cross", "quantity", parameters["quantity"])

    if short_window >= long_window:
        raise ValueError("moving_average_cross short_window must be less than long_window")

    return parameters


class StrategyBase(BaseModel):
    name: NonEmptyStr
    description: str | None = None
    symbol: NonEmptyStr
    timeframe: NonEmptyStr
    strategy_type: StrategyType = "price_threshold"
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_parameters_for_type(self) -> "StrategyBase":
        if self.strategy_type == "price_threshold":
            validate_price_threshold_parameters(self.parameters)
        if self.strategy_type == "moving_average_cross":
            validate_moving_average_cross_parameters(self.parameters)
        return self


class StrategyCreate(StrategyBase):
    pass


class StrategyUpdate(BaseModel):
    name: NonEmptyStr | None = None
    description: str | None = None
    symbol: NonEmptyStr | None = None
    timeframe: NonEmptyStr | None = None
    strategy_type: StrategyType | None = None
    parameters: dict[str, Any] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_parameters_for_type(self) -> "StrategyUpdate":
        strategy_type = self.strategy_type or "price_threshold"
        if strategy_type == "price_threshold" and self.parameters is not None:
            validate_price_threshold_parameters(self.parameters)
        if strategy_type == "moving_average_cross" and self.parameters is not None:
            validate_moving_average_cross_parameters(self.parameters)
        return self


class StrategyRead(StrategyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
