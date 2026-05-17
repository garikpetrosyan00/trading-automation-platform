from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Body, Query

from app.api.dependencies import DbSession
from app.core.errors import AppError
from app.repositories.backtest_run import BacktestRunRepository
from app.repositories.market_candle import MarketCandleRepository
from app.repositories.strategy import StrategyRepository
from app.schemas.backtest import (
    BACKTEST_OPTIMIZATION_RESPONSE_EXAMPLE,
    BOLLINGER_BANDS_OPTIMIZATION_REQUEST_EXAMPLE,
    BacktestOptimizationRequest,
    BacktestOptimizationResponse,
    BacktestOptimizationResultResponse,
    BacktestResultResponse,
    BacktestRunHistoryResponse,
    BacktestRunRequest,
    BacktestTradeResponse,
    MOVING_AVERAGE_CROSS_OPTIMIZATION_REQUEST_EXAMPLE,
    PRICE_THRESHOLD_OPTIMIZATION_REQUEST_EXAMPLE,
    RSI_THRESHOLD_OPTIMIZATION_REQUEST_EXAMPLE,
)
from app.schemas.strategy import (
    validate_bollinger_bands_parameters,
    validate_moving_average_cross_parameters,
    validate_price_threshold_parameters,
    validate_rsi_threshold_parameters,
)
from app.services.backtest import BacktestService
from app.services.strategy import StrategyService

router = APIRouter()

PRICE_THRESHOLD_STRATEGY_TYPE = "price_threshold"
MOVING_AVERAGE_CROSS_STRATEGY_TYPE = "moving_average_cross"
RSI_THRESHOLD_STRATEGY_TYPE = "rsi_threshold"
BOLLINGER_BANDS_STRATEGY_TYPE = "bollinger_bands"


def get_strategy_service(db: DbSession) -> StrategyService:
    return StrategyService(StrategyRepository(db))


def get_backtest_service(db: DbSession) -> BacktestService:
    return BacktestService(MarketCandleRepository(db), BacktestRunRepository(db))


def positive_decimal_parameter(parameters: dict[str, Any], key: str) -> Decimal:
    if key not in parameters:
        raise AppError(
            f"Parameter '{key}' is required",
            status_code=422,
            error_code="invalid_optimization_parameters",
        )
    try:
        value = Decimal(str(parameters[key]))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppError(
            f"Parameter '{key}' must be a positive number",
            status_code=422,
            error_code="invalid_optimization_parameters",
        ) from exc
    if not value.is_finite() or value <= 0:
        raise AppError(
            f"Parameter '{key}' must be a positive number",
            status_code=422,
            error_code="invalid_optimization_parameters",
        )
    return value


def positive_integer_parameter(parameters: dict[str, Any], key: str) -> int:
    value = positive_decimal_parameter(parameters, key)
    if value != value.to_integral_value():
        raise AppError(
            f"Parameter '{key}' must be a positive integer",
            status_code=422,
            error_code="invalid_optimization_parameters",
        )
    return int(value)


def validate_optimization_parameters(
    *,
    strategy_type: str,
    parameters: dict[str, Any],
    index: int,
) -> None:
    try:
        if strategy_type == PRICE_THRESHOLD_STRATEGY_TYPE:
            validate_price_threshold_parameters(parameters)
        elif strategy_type == MOVING_AVERAGE_CROSS_STRATEGY_TYPE:
            validate_moving_average_cross_parameters(parameters)
        elif strategy_type == RSI_THRESHOLD_STRATEGY_TYPE:
            validate_rsi_threshold_parameters(parameters)
        elif strategy_type == BOLLINGER_BANDS_STRATEGY_TYPE:
            validate_bollinger_bands_parameters(parameters)
    except ValueError as exc:
        raise AppError(
            f"parameter_sets[{index}]: {exc}",
            status_code=422,
            error_code="invalid_optimization_parameters",
        ) from exc


def normalize_optimization_parameters(
    strategy_type: str,
    parameters: dict[str, Any],
    *,
    base_parameters: dict[str, Any] | None = None,
    index: int,
) -> dict[str, str]:
    if strategy_type == PRICE_THRESHOLD_STRATEGY_TYPE:
        try:
            normalized = dict(parameters)
            if "buy_below" not in normalized and "entry_below" in normalized:
                normalized["buy_below"] = normalized["entry_below"]
            if "sell_above" not in normalized and "exit_above" in normalized:
                normalized["sell_above"] = normalized["exit_above"]
            normalized = {
                key: str(positive_decimal_parameter(normalized, key))
                for key in ("buy_below", "sell_above", "quantity")
                if key in normalized
            }
        except AppError as exc:
            raise AppError(
                f"parameter_sets[{index}]: {exc.message}",
                status_code=422,
                error_code="invalid_optimization_parameters",
            ) from exc
        validate_optimization_parameters(
            strategy_type=strategy_type,
            parameters={**(base_parameters or {}), **normalized},
            index=index,
        )
        return normalized

    if strategy_type == MOVING_AVERAGE_CROSS_STRATEGY_TYPE:
        try:
            normalized = {}
            if "short_window" in parameters:
                normalized["short_window"] = str(positive_integer_parameter(parameters, "short_window"))
            if "long_window" in parameters:
                normalized["long_window"] = str(positive_integer_parameter(parameters, "long_window"))
            if "quantity" in parameters:
                normalized["quantity"] = str(positive_decimal_parameter(parameters, "quantity"))
        except AppError as exc:
            raise AppError(
                f"parameter_sets[{index}]: {exc.message}",
                status_code=422,
                error_code="invalid_optimization_parameters",
            ) from exc
        validate_optimization_parameters(
            strategy_type=strategy_type,
            parameters={**(base_parameters or {}), **normalized},
            index=index,
        )
        return normalized

    if strategy_type == RSI_THRESHOLD_STRATEGY_TYPE:
        try:
            normalized = {}
            if "period" in parameters:
                normalized["period"] = str(positive_integer_parameter(parameters, "period"))
            if "oversold" in parameters:
                normalized["oversold"] = str(positive_decimal_parameter(parameters, "oversold"))
            if "overbought" in parameters:
                normalized["overbought"] = str(positive_decimal_parameter(parameters, "overbought"))
            if "quantity" in parameters:
                normalized["quantity"] = str(positive_decimal_parameter(parameters, "quantity"))
        except AppError as exc:
            raise AppError(
                f"parameter_sets[{index}]: {exc.message}",
                status_code=422,
                error_code="invalid_optimization_parameters",
            ) from exc
        validate_optimization_parameters(
            strategy_type=strategy_type,
            parameters={**(base_parameters or {}), **normalized},
            index=index,
        )
        return normalized

    if strategy_type == BOLLINGER_BANDS_STRATEGY_TYPE:
        try:
            normalized = {}
            if "period" in parameters:
                normalized["period"] = str(positive_integer_parameter(parameters, "period"))
            if "stddev_multiplier" in parameters:
                normalized["stddev_multiplier"] = str(positive_decimal_parameter(parameters, "stddev_multiplier"))
            if "quantity" in parameters:
                normalized["quantity"] = str(positive_decimal_parameter(parameters, "quantity"))
        except AppError as exc:
            raise AppError(
                f"parameter_sets[{index}]: {exc.message}",
                status_code=422,
                error_code="invalid_optimization_parameters",
            ) from exc
        validate_optimization_parameters(
            strategy_type=strategy_type,
            parameters={**(base_parameters or {}), **normalized},
            index=index,
        )
        return normalized

    raise AppError(
        f"Strategy type '{strategy_type}' is not supported for optimization",
        status_code=422,
        error_code="unsupported_optimization_strategy_type",
    )


def metric_sort_value(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal("-Infinity")


def optimization_quality(
    result: Any,
    *,
    min_closed_trades: int = 0,
    require_closed_position: bool = False,
) -> dict[str, Any]:
    warnings: list[str] = []
    if result.closed_trades == 0:
        warnings.append("no_closed_trades")
    if result.closed_trades < min_closed_trades:
        warnings.append("below_min_closed_trades")
    if result.open_position:
        warnings.append("ends_with_open_position")
    if require_closed_position and result.open_position:
        warnings.append("requires_closed_position")

    return {
        "has_closed_trades": result.closed_trades > 0,
        "has_open_position": result.open_position,
        "passes_quality_filters": result.closed_trades >= min_closed_trades
        and (not require_closed_position or not result.open_position),
        "quality_warnings": warnings,
    }


def ranked_optimization_results(
    results: list[tuple[int, dict[str, Any], dict[str, str], dict[str, Any], Any, dict[str, Any]]],
) -> list[tuple[int, dict[str, Any], dict[str, str], dict[str, Any], Any, dict[str, Any]]]:
    return sorted(
        results,
        key=lambda item: (
            item[5]["passes_quality_filters"],
            metric_sort_value(item[4].total_return_percent),
            metric_sort_value(item[4].total_return),
            Decimal(item[4].closed_trades),
            Decimal(-item[0]),
        ),
        reverse=True,
    )


@router.post("", response_model=BacktestResultResponse)
async def run_backtest(payload: BacktestRunRequest, db: DbSession) -> BacktestResultResponse:
    strategy = get_strategy_service(db).get_by_id(payload.strategy_id)
    result, _ = get_backtest_service(db).run_and_persist(
        strategy=strategy,
        initial_balance=payload.initial_balance,
        source=payload.source,
    )

    return BacktestResultResponse(
        strategy_id=strategy.id,
        symbol=result.symbol,
        timeframe=result.timeframe,
        strategy_type=result.strategy_type,
        source=result.source,
        initial_balance=result.initial_balance,
        cash_balance=result.cash_balance,
        position_quantity=result.position_quantity,
        entry_price=result.entry_price,
        final_balance=result.final_balance,
        realized_pnl=result.realized_pnl,
        unrealized_pnl=result.unrealized_pnl,
        number_of_trades=result.number_of_trades,
        closed_trades=result.closed_trades,
        open_position=result.open_position,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        candles_processed=result.candles_processed,
        total_return=result.total_return,
        total_return_percent=result.total_return_percent,
        win_rate=result.win_rate,
        average_trade_pnl=result.average_trade_pnl,
        best_trade_pnl=result.best_trade_pnl,
        worst_trade_pnl=result.worst_trade_pnl,
        profit_factor=result.profit_factor,
        trades=[BacktestTradeResponse.model_validate(trade) for trade in result.trades],
    )


@router.post(
    "/optimize",
    response_model=BacktestOptimizationResponse,
    responses={
        200: {
            "description": "Ranked optimization results with performance metrics and quality audit metadata.",
            "content": {
                "application/json": {
                    "examples": {
                        "with_quality_warnings": {
                            "summary": "Optimization response with audit metadata and warnings",
                            "value": BACKTEST_OPTIMIZATION_RESPONSE_EXAMPLE,
                        }
                    }
                }
            },
        }
    },
)
async def optimize_backtest(
    payload: Annotated[
        BacktestOptimizationRequest,
        Body(
            openapi_examples={
                "price_threshold": {
                    "summary": "Price threshold candidate overrides",
                    "description": (
                        "Optimizes price thresholds and quantity while preserving the saved strategy parameters."
                    ),
                    "value": PRICE_THRESHOLD_OPTIMIZATION_REQUEST_EXAMPLE,
                },
                "moving_average_cross": {
                    "summary": "Moving average cross candidate overrides",
                    "description": (
                        "Optimizes moving average windows and quantity with quality filters included."
                    ),
                    "value": MOVING_AVERAGE_CROSS_OPTIMIZATION_REQUEST_EXAMPLE,
                },
                "rsi_threshold": {
                    "summary": "RSI threshold candidate overrides",
                    "description": (
                        "Optimizes RSI period, threshold levels, and quantity while preserving base strategy parameters."
                    ),
                    "value": RSI_THRESHOLD_OPTIMIZATION_REQUEST_EXAMPLE,
                },
                "bollinger_bands": {
                    "summary": "Bollinger Bands candidate overrides",
                    "description": (
                        "Optimizes Bollinger period, standard deviation multiplier, and quantity."
                    ),
                    "value": BOLLINGER_BANDS_OPTIMIZATION_REQUEST_EXAMPLE,
                },
            }
        ),
    ],
    db: DbSession,
) -> BacktestOptimizationResponse:
    strategy = get_strategy_service(db).get_by_id(payload.strategy_id)
    strategy_type = strategy.strategy_type or PRICE_THRESHOLD_STRATEGY_TYPE
    base_parameters = dict(strategy.parameters or {})
    optimization_candidates = [
        (
            index,
            dict(submitted_parameters),
            normalized_parameters,
            {**base_parameters, **normalized_parameters},
        )
        for index, submitted_parameters in enumerate(payload.parameter_sets)
        for normalized_parameters in [
            normalize_optimization_parameters(
                strategy_type,
                submitted_parameters,
                base_parameters=base_parameters,
                index=index,
            )
        ]
    ]
    backtest_service = get_backtest_service(db)
    raw_results = [
        (
            index,
            submitted_parameters,
            parameter_overrides,
            effective_parameters,
            backtest_service.run(
                strategy=strategy,
                initial_balance=payload.initial_balance,
                source=payload.source,
                parameter_overrides=parameter_overrides,
            ),
        )
        for index, submitted_parameters, parameter_overrides, effective_parameters in optimization_candidates
    ]
    raw_results_with_quality = [
        (
            index,
            submitted_parameters,
            parameter_overrides,
            effective_parameters,
            result,
            optimization_quality(
                result,
                min_closed_trades=payload.min_closed_trades,
                require_closed_position=payload.require_closed_position,
            ),
        )
        for index, submitted_parameters, parameter_overrides, effective_parameters, result in raw_results
    ]

    ranked = ranked_optimization_results(raw_results_with_quality)
    first_result = raw_results[0][4]
    results = [
        BacktestOptimizationResultResponse(
            rank=rank,
            parameters=parameter_overrides,
            base_parameters=base_parameters,
            parameter_overrides=submitted_parameters,
            effective_parameters=effective_parameters,
            final_balance=result.final_balance,
            total_return=result.total_return,
            total_return_percent=result.total_return_percent,
            win_rate=result.win_rate,
            profit_factor=result.profit_factor,
            number_of_trades=result.number_of_trades,
            closed_trades=result.closed_trades,
            open_position=result.open_position,
            position_quantity=result.position_quantity,
            entry_price=result.entry_price,
            has_closed_trades=quality["has_closed_trades"],
            has_open_position=quality["has_open_position"],
            passes_quality_filters=quality["passes_quality_filters"],
            quality_warnings=quality["quality_warnings"],
        )
        for rank, (
            _,
            submitted_parameters,
            parameter_overrides,
            effective_parameters,
            result,
            quality,
        ) in enumerate(ranked, start=1)
    ]

    return BacktestOptimizationResponse(
        strategy_id=strategy.id,
        symbol=first_result.symbol,
        timeframe=first_result.timeframe,
        strategy_type=first_result.strategy_type,
        source=first_result.source,
        initial_balance=payload.initial_balance,
        total_runs=len(results),
        results=results,
    )


@router.get("", response_model=list[BacktestRunHistoryResponse])
async def list_backtests(
    db: DbSession,
    strategy_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[BacktestRunHistoryResponse]:
    runs = get_backtest_service(db).list_recent(strategy_id=strategy_id, limit=limit)
    return [BacktestRunHistoryResponse.model_validate(run) for run in runs]
