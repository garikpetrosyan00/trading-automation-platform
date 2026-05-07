from fastapi import APIRouter

from app.api.dependencies import DbSession
from app.engine.backtesting import BacktestingEngine
from app.repositories.market_candle import MarketCandleRepository
from app.repositories.strategy import StrategyRepository
from app.schemas.backtest import BacktestResultResponse, BacktestRunRequest, BacktestTradeResponse
from app.services.strategy import StrategyService

router = APIRouter()


def get_strategy_service(db: DbSession) -> StrategyService:
    return StrategyService(StrategyRepository(db))


@router.post("", response_model=BacktestResultResponse)
async def run_backtest(payload: BacktestRunRequest, db: DbSession) -> BacktestResultResponse:
    strategy = get_strategy_service(db).get_by_id(payload.strategy_id)
    result = BacktestingEngine(MarketCandleRepository(db)).run(
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
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        candles_processed=result.candles_processed,
        trades=[BacktestTradeResponse.model_validate(trade) for trade in result.trades],
    )
