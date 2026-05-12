from decimal import Decimal

from app.engine.backtesting import BacktestingEngine, BacktestResult
from app.models.backtest_run import BacktestRun
from app.models.strategy import Strategy
from app.repositories.backtest_run import BacktestRunRepository
from app.repositories.market_candle import MarketCandleRepository


class BacktestService:
    def __init__(
        self,
        market_candle_repository: MarketCandleRepository,
        backtest_run_repository: BacktestRunRepository,
    ):
        self.market_candle_repository = market_candle_repository
        self.backtest_run_repository = backtest_run_repository

    def run_and_persist(
        self,
        *,
        strategy: Strategy,
        initial_balance: Decimal,
        source: str | None = None,
    ) -> tuple[BacktestResult, BacktestRun]:
        result = BacktestingEngine(self.market_candle_repository).run(
            strategy=strategy,
            initial_balance=initial_balance,
            source=source,
        )
        backtest_run = BacktestRun(
            strategy_id=strategy.id,
            symbol=result.symbol,
            timeframe=result.timeframe,
            strategy_type=result.strategy_type,
            source=result.source,
            initial_balance=result.initial_balance,
            final_balance=result.final_balance,
            cash_balance=result.cash_balance,
            realized_pnl=result.realized_pnl,
            unrealized_pnl=result.unrealized_pnl,
            number_of_trades=result.number_of_trades,
            closed_trades=result.closed_trades,
            open_position=result.open_position,
            position_quantity=result.position_quantity,
            entry_price=result.entry_price,
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
        )
        return result, self.backtest_run_repository.create(backtest_run)

    def list_recent(self, *, strategy_id: int | None = None, limit: int = 50) -> list[BacktestRun]:
        return self.backtest_run_repository.list_recent(strategy_id=strategy_id, limit=limit)
