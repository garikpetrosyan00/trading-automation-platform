from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PLACEHOLDER_STRING = "string"
PlaceholderSafeStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(lambda value: reject_placeholder_string(value)),
]
StrategyType = Literal["price_threshold", "moving_average_cross"]
PRICE_THRESHOLD_PARAMETER_KEYS = ("buy_below", "sell_above", "quantity")
MOVING_AVERAGE_CROSS_PARAMETER_KEYS = ("short_window", "long_window", "quantity")


def reject_placeholder_string(value: str) -> str:
    if value.strip().lower() == PLACEHOLDER_STRING:
        raise ValueError("must not be the placeholder value 'string'")
    return value


def validate_price_threshold_parameters(parameters: dict[str, Any] | None) -> dict[str, Any] | None:
    if not parameters:
        return parameters

    parsed_values: dict[str, Decimal] = {}
    for key in PRICE_THRESHOLD_PARAMETER_KEYS:
        if key not in parameters:
            continue
        try:
            value = Decimal(str(parameters[key]))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"price_threshold parameter {key} must be a positive number") from exc

        if not value.is_finite() or value <= Decimal("0"):
            raise ValueError(f"price_threshold parameter {key} must be a positive number")
        parsed_values[key] = value

    if (
        "buy_below" in parsed_values
        and "sell_above" in parsed_values
        and parsed_values["buy_below"] >= parsed_values["sell_above"]
    ):
        raise ValueError("price_threshold sell_above must be greater than buy_below")

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

    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{strategy_type} parameter {key} must be a positive integer") from exc

    if not parsed.is_finite() or parsed <= Decimal("0") or parsed != parsed.to_integral_value():
        raise ValueError(f"{strategy_type} parameter {key} must be a positive integer")
    return int(parsed)


def validate_moving_average_cross_parameters(parameters: dict[str, Any] | None) -> dict[str, Any] | None:
    if not parameters:
        return parameters

    short_window = (
        _parse_positive_integer(
            "moving_average_cross",
            "short_window",
            parameters["short_window"],
        )
        if "short_window" in parameters
        else None
    )
    long_window = (
        _parse_positive_integer(
            "moving_average_cross",
            "long_window",
            parameters["long_window"],
        )
        if "long_window" in parameters
        else None
    )
    if "quantity" in parameters:
        _parse_positive_number("moving_average_cross", "quantity", parameters["quantity"])

    if short_window is not None and long_window is not None and short_window >= long_window:
        raise ValueError("moving_average_cross short_window must be less than long_window")

    return parameters


class StrategyBase(BaseModel):
    name: PlaceholderSafeStr
    description: str | None = None
    symbol: PlaceholderSafeStr
    timeframe: PlaceholderSafeStr
    strategy_type: StrategyType = "price_threshold"
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class StrategyCreate(StrategyBase):
    pass


class StrategyUpdate(BaseModel):
    name: PlaceholderSafeStr | None = None
    description: str | None = None
    symbol: PlaceholderSafeStr | None = None
    timeframe: PlaceholderSafeStr | None = None
    strategy_type: StrategyType | None = None
    parameters: dict[str, Any] | None = None
    is_active: bool | None = None


class StrategyRead(StrategyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
