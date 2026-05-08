from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import DbSession
from app.repositories.backtest_run import BacktestRunRepository
from app.repositories.market_candle import MarketCandleRepository
from app.repositories.strategy import StrategyRepository
from app.schemas.backtest import (
    BacktestResultResponse,
    BacktestRunHistoryResponse,
    BacktestRunRequest,
    BacktestTradeResponse,
)
from app.services.backtest import BacktestService
from app.services.strategy import StrategyService

router = APIRouter()


def get_strategy_service(db: DbSession) -> StrategyService:
    return StrategyService(StrategyRepository(db))


def get_backtest_service(db: DbSession) -> BacktestService:
    return BacktestService(MarketCandleRepository(db), BacktestRunRepository(db))


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
        trades=[BacktestTradeResponse.model_validate(trade) for trade in result.trades],
    )


@router.get("", response_model=list[BacktestRunHistoryResponse])
async def list_backtests(
    db: DbSession,
    strategy_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[BacktestRunHistoryResponse]:
    runs = get_backtest_service(db).list_recent(strategy_id=strategy_id, limit=limit)
    return [BacktestRunHistoryResponse.model_validate(run) for run in runs]
