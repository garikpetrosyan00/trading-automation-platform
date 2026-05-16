from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.dependencies import DbSession
from app.core.errors import AppError
from app.repositories.backtest_run import BacktestRunRepository
from app.repositories.market_candle import MarketCandleRepository
from app.repositories.strategy import StrategyRepository
from app.schemas.backtest import (
    BacktestOptimizationRequest,
    BacktestOptimizationResponse,
    BacktestOptimizationResultResponse,
    BacktestResultResponse,
    BacktestRunHistoryResponse,
    BacktestRunRequest,
    BacktestTradeResponse,
)
from app.services.backtest import BacktestService
from app.services.strategy import StrategyService

router = APIRouter()

PRICE_THRESHOLD_STRATEGY_TYPE = "price_threshold"
MOVING_AVERAGE_CROSS_STRATEGY_TYPE = "moving_average_cross"


def get_strategy_service(db: DbSession) -> StrategyService:
    return StrategyService(StrategyRepository(db))


def get_backtest_service(db: DbSession) -> BacktestService:
    return BacktestService(MarketCandleRepository(db), BacktestRunRepository(db))


def positive_decimal_parameter(parameters: dict[str, Any], key: str) -> Decimal:
    if key not in parameters:
        raise AppError(f"Parameter '{key}' is required", status_code=422, error_code="invalid_optimization_parameters")
    try:
        value = Decimal(str(parameters[key]))
    except (InvalidOperation, ValueError) as exc:
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


def normalize_optimization_parameters(strategy_type: str, parameters: dict[str, Any]) -> dict[str, str]:
    if strategy_type == PRICE_THRESHOLD_STRATEGY_TYPE:
        normalized = dict(parameters)
        if "buy_below" not in normalized and "entry_below" in normalized:
            normalized["buy_below"] = normalized["entry_below"]
        if "sell_above" not in normalized and "exit_above" in normalized:
            normalized["sell_above"] = normalized["exit_above"]
        return {
            "buy_below": str(positive_decimal_parameter(normalized, "buy_below")),
            "sell_above": str(positive_decimal_parameter(normalized, "sell_above")),
            "quantity": str(positive_decimal_parameter(normalized, "quantity")),
        }

    if strategy_type == MOVING_AVERAGE_CROSS_STRATEGY_TYPE:
        short_window = positive_integer_parameter(parameters, "short_window")
        long_window = positive_integer_parameter(parameters, "long_window")
        if short_window >= long_window:
            raise AppError(
                "Parameter 'short_window' must be smaller than 'long_window'",
                status_code=422,
                error_code="invalid_optimization_parameters",
            )
        return {
            "short_window": str(short_window),
            "long_window": str(long_window),
            "quantity": str(positive_decimal_parameter(parameters, "quantity")),
        }

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
    results: list[tuple[int, dict[str, str], Any, dict[str, Any]]],
) -> list[tuple[int, dict[str, str], Any, dict[str, Any]]]:
    return sorted(
        results,
        key=lambda item: (
            item[3]["passes_quality_filters"],
            metric_sort_value(item[2].total_return_percent),
            metric_sort_value(item[2].total_return),
            Decimal(item[2].closed_trades),
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


@router.post("/optimize", response_model=BacktestOptimizationResponse)
async def optimize_backtest(payload: BacktestOptimizationRequest, db: DbSession) -> BacktestOptimizationResponse:
    strategy = get_strategy_service(db).get_by_id(payload.strategy_id)
    strategy_type = strategy.strategy_type or PRICE_THRESHOLD_STRATEGY_TYPE
    normalized_parameter_sets = [
        normalize_optimization_parameters(strategy_type, parameters)
        for parameters in payload.parameter_sets
    ]
    backtest_service = get_backtest_service(db)
    raw_results = [
        (
            index,
            parameters,
            backtest_service.run(
                strategy=strategy,
                initial_balance=payload.initial_balance,
                source=payload.source,
                parameter_overrides=parameters,
            ),
        )
        for index, parameters in enumerate(normalized_parameter_sets)
    ]
    raw_results_with_quality = [
        (
            index,
            parameters,
            result,
            optimization_quality(
                result,
                min_closed_trades=payload.min_closed_trades,
                require_closed_position=payload.require_closed_position,
            ),
        )
        for index, parameters, result in raw_results
    ]

    ranked = ranked_optimization_results(raw_results_with_quality)
    first_result = raw_results[0][2]
    results = [
        BacktestOptimizationResultResponse(
            rank=rank,
            parameters=parameters,
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
        for rank, (_, parameters, result, quality) in enumerate(ranked, start=1)
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
