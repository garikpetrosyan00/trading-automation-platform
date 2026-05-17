from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveDecimal = Annotated[Decimal, Field(gt=0)]

PRICE_THRESHOLD_OPTIMIZATION_REQUEST_EXAMPLE = {
    "strategy_id": 42,
    "initial_balance": "10000",
    "source": "manual",
    "min_closed_trades": 2,
    "require_closed_position": True,
    "parameter_sets": [
        {"buy_below": "65000", "sell_above": "69000", "quantity": "0.05"},
        {"buy_below": "64000", "sell_above": "70000", "quantity": "0.05"},
        {"quantity": "0.03"},
    ],
}

MOVING_AVERAGE_CROSS_OPTIMIZATION_REQUEST_EXAMPLE = {
    "strategy_id": 84,
    "initial_balance": "25000",
    "source": "binance",
    "min_closed_trades": 3,
    "require_closed_position": False,
    "parameter_sets": [
        {"short_window": "5", "long_window": "20", "quantity": "0.10"},
        {"short_window": "8", "long_window": "34", "quantity": "0.08"},
        {"short_window": "13", "long_window": "55"},
    ],
}

BACKTEST_OPTIMIZATION_RESPONSE_EXAMPLE = {
    "strategy_id": 42,
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "strategy_type": "price_threshold",
    "source": "manual",
    "initial_balance": "10000",
    "total_runs": 3,
    "results": [
        {
            "rank": 1,
            "parameters": {"buy_below": "65000", "sell_above": "69000", "quantity": "0.05"},
            "base_parameters": {"buy_below": "66000", "sell_above": "70500", "quantity": "0.04"},
            "parameter_overrides": {"buy_below": "65000", "sell_above": "69000", "quantity": "0.05"},
            "effective_parameters": {"buy_below": "65000", "sell_above": "69000", "quantity": "0.05"},
            "final_balance": "10575.00000000",
            "total_return": "575.00000000",
            "total_return_percent": "5.75000000",
            "win_rate": "66.66666667",
            "profit_factor": "2.87500000",
            "number_of_trades": 6,
            "closed_trades": 3,
            "open_position": False,
            "position_quantity": "0",
            "entry_price": None,
            "has_closed_trades": True,
            "has_open_position": False,
            "passes_quality_filters": True,
            "quality_warnings": [],
        },
        {
            "rank": 2,
            "parameters": {"quantity": "0.03"},
            "base_parameters": {"buy_below": "66000", "sell_above": "70500", "quantity": "0.04"},
            "parameter_overrides": {"quantity": "0.03"},
            "effective_parameters": {"buy_below": "66000", "sell_above": "70500", "quantity": "0.03"},
            "final_balance": "10120.00000000",
            "total_return": "120.00000000",
            "total_return_percent": "1.20000000",
            "win_rate": None,
            "profit_factor": None,
            "number_of_trades": 1,
            "closed_trades": 0,
            "open_position": True,
            "position_quantity": "0.03",
            "entry_price": "66000.00000000",
            "has_closed_trades": False,
            "has_open_position": True,
            "passes_quality_filters": False,
            "quality_warnings": [
                "no_closed_trades",
                "below_min_closed_trades",
                "ends_with_open_position",
                "requires_closed_position",
            ],
        },
    ],
}


class BacktestRunRequest(BaseModel):
    strategy_id: int = Field(description="Identifier of the strategy to backtest.")
    initial_balance: PositiveDecimal = Field(description="Starting cash balance for each simulated run.")
    source: NonEmptyStr | None = Field(
        default=None,
        description="Optional market data source filter. When omitted, all matching candles may be used.",
    )


class BacktestOptimizationRequest(BacktestRunRequest):
    parameter_sets: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=50,
        description=(
            "Candidate parameter overrides to evaluate. Each item is merged with the saved strategy "
            "parameters for that run and does not mutate the strategy."
        ),
    )
    min_closed_trades: int = Field(
        default=0,
        ge=0,
        description="Minimum number of closed trades required for passes_quality_filters to be true.",
    )
    require_closed_position: bool = Field(
        default=False,
        description="When true, candidates ending with an open position fail the quality filter.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                PRICE_THRESHOLD_OPTIMIZATION_REQUEST_EXAMPLE,
                MOVING_AVERAGE_CROSS_OPTIMIZATION_REQUEST_EXAMPLE,
            ]
        }
    )


class BacktestTradeResponse(BaseModel):
    decision: str
    side: str
    symbol: str
    quantity: Decimal
    price: Decimal
    opened_at: datetime
    cash_balance: Decimal
    position_quantity: Decimal
    realized_pnl: Decimal
    decision_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BacktestResultResponse(BaseModel):
    strategy_id: int
    symbol: str
    timeframe: str
    strategy_type: str
    source: str | None = None
    initial_balance: Decimal
    cash_balance: Decimal
    position_quantity: Decimal
    entry_price: Decimal | None
    final_balance: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    number_of_trades: int
    closed_trades: int
    open_position: bool
    winning_trades: int
    losing_trades: int
    candles_processed: int
    total_return: Decimal
    total_return_percent: Decimal | None = None
    win_rate: Decimal | None = None
    average_trade_pnl: Decimal | None = None
    best_trade_pnl: Decimal | None = None
    worst_trade_pnl: Decimal | None = None
    profit_factor: Decimal | None = None
    trades: list[BacktestTradeResponse]

    model_config = ConfigDict(from_attributes=True)


class BacktestRunHistoryResponse(BaseModel):
    id: int
    strategy_id: int
    symbol: str
    timeframe: str
    strategy_type: str
    source: str | None = None
    initial_balance: Decimal
    final_balance: Decimal
    cash_balance: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    number_of_trades: int
    closed_trades: int
    open_position: bool
    position_quantity: Decimal
    entry_price: Decimal | None
    winning_trades: int
    losing_trades: int
    candles_processed: int
    total_return: Decimal | None = None
    total_return_percent: Decimal | None = None
    win_rate: Decimal | None = None
    average_trade_pnl: Decimal | None = None
    best_trade_pnl: Decimal | None = None
    worst_trade_pnl: Decimal | None = None
    profit_factor: Decimal | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestOptimizationResultResponse(BaseModel):
    rank: int = Field(description="One-based rank after sorting candidates by optimization score.")
    parameters: dict[str, Any] = Field(
        description="Normalized candidate overrides that were passed into the backtest engine."
    )
    base_parameters: dict[str, Any] = Field(description="Saved strategy parameters before candidate overrides.")
    parameter_overrides: dict[str, Any] = Field(description="Original candidate overrides submitted in parameter_sets.")
    effective_parameters: dict[str, Any] = Field(
        description="Full parameter set used for the run after merging base_parameters and normalized overrides."
    )
    final_balance: Decimal = Field(description="Ending account value for the candidate run.")
    total_return: Decimal = Field(description="Absolute profit or loss for the candidate run.")
    total_return_percent: Decimal | None = Field(default=None, description="Percent return relative to initial_balance.")
    win_rate: Decimal | None = Field(default=None, description="Percent of closed trades that were profitable.")
    profit_factor: Decimal | None = Field(
        default=None,
        description="Gross profit divided by gross loss when enough closed trade data exists.",
    )
    number_of_trades: int = Field(description="Total simulated orders generated by the candidate run.")
    closed_trades: int = Field(description="Number of completed round-trip trades.")
    open_position: bool = Field(description="Whether the candidate run ended with an open position.")
    position_quantity: Decimal = Field(description="Remaining open position quantity at the end of the run.")
    entry_price: Decimal | None = Field(default=None, description="Average entry price for any remaining open position.")
    has_closed_trades: bool = Field(description="Whether the candidate produced at least one closed trade.")
    has_open_position: bool = Field(description="Whether the candidate ended with an open position.")
    passes_quality_filters: bool = Field(
        description="Whether the candidate satisfies min_closed_trades and require_closed_position."
    )
    quality_warnings: list[str] = Field(
        description="Audit warnings explaining sparse or incomplete candidate results."
    )


class BacktestOptimizationResponse(BaseModel):
    strategy_id: int = Field(description="Identifier of the optimized strategy.")
    symbol: str = Field(description="Market symbol used for the optimization runs.")
    timeframe: str = Field(description="Candle timeframe used for the optimization runs.")
    strategy_type: str = Field(description="Strategy implementation used to evaluate each candidate.")
    source: str | None = Field(default=None, description="Market data source used by the optimization runs.")
    initial_balance: Decimal = Field(description="Starting cash balance used for every candidate run.")
    total_runs: int = Field(description="Number of candidate runs evaluated.")
    results: list[BacktestOptimizationResultResponse] = Field(
        description="Ranked candidate results including performance metrics and quality audit metadata."
    )

    model_config = ConfigDict(json_schema_extra={"examples": [BACKTEST_OPTIMIZATION_RESPONSE_EXAMPLE]})
