from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from app.engine.strategy_engine import StrategyDecision, StrategyEngine
from app.repositories.market_candle import MarketCandleRepository

ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class BacktestTrade:
    side: str
    symbol: str
    quantity: Decimal
    price: Decimal
    opened_at: datetime
    cash_balance: Decimal
    position_quantity: Decimal
    realized_pnl: Decimal = ZERO
    decision_reason: str | None = None

    @property
    def decision(self) -> str:
        return self.side


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    timeframe: str
    strategy_type: str
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
    total_return_percent: Decimal | None
    win_rate: Decimal | None
    average_trade_pnl: Decimal | None
    best_trade_pnl: Decimal | None
    worst_trade_pnl: Decimal | None
    profit_factor: Decimal | None
    source: str | None = None
    trades: list[BacktestTrade] = field(default_factory=list)
    decisions: list[StrategyDecision] = field(default_factory=list)


class BacktestingEngine:
    def __init__(self, market_candle_repository: MarketCandleRepository):
        self.market_candle_repository = market_candle_repository

    def run(
        self,
        *,
        strategy,
        initial_balance: Decimal,
        source: str | None = None,
        profile=None,
    ) -> BacktestResult:
        strategy_type = StrategyEngine.strategy_type(strategy)
        symbol = strategy.symbol
        timeframe = strategy.timeframe
        parameters = strategy.parameters or {}
        candle_source = source if source is not None else self._strategy_candle_source(parameters)
        candles = self.market_candle_repository.list_history(
            symbol=symbol,
            timeframe=timeframe,
            source=candle_source,
        )

        cash_balance = initial_balance
        position_quantity = ZERO
        entry_price: Decimal | None = None
        realized_pnl = ZERO
        closed_trades = 0
        winning_trades = 0
        losing_trades = 0
        trades: list[BacktestTrade] = []
        decisions: list[StrategyDecision] = []
        strategy_profile = profile or SimpleNamespace(entry_below=None, exit_above=None, order_quantity=None)

        for index, candle in enumerate(candles):
            visible_candles = candles[: index + 1]
            decision = StrategyEngine.evaluate(
                strategy_type=strategy_type,
                parameters=parameters,
                profile=strategy_profile,
                latest_price=candle.close_price,
                position_quantity=position_quantity,
                candles=visible_candles,
            )
            decisions.append(decision)

            if decision.decision == "buy" and position_quantity <= ZERO:
                quantity = decision.metadata.get("_order_quantity")
                if quantity is None:
                    continue
                cost = quantity * candle.close_price
                if cost > cash_balance:
                    continue
                cash_balance -= cost
                position_quantity = quantity
                entry_price = candle.close_price
                trades.append(
                    BacktestTrade(
                        side="buy",
                        symbol=symbol,
                        quantity=quantity,
                        price=candle.close_price,
                        opened_at=candle.close_time,
                        cash_balance=cash_balance,
                        position_quantity=position_quantity,
                        decision_reason=decision.reason,
                    )
                )
                continue

            if decision.decision == "sell" and position_quantity > ZERO and entry_price is not None:
                proceeds = position_quantity * candle.close_price
                trade_pnl = (candle.close_price - entry_price) * position_quantity
                cash_balance += proceeds
                realized_pnl += trade_pnl
                closed_trades += 1
                if trade_pnl > ZERO:
                    winning_trades += 1
                elif trade_pnl < ZERO:
                    losing_trades += 1
                trades.append(
                    BacktestTrade(
                        side="sell",
                        symbol=symbol,
                        quantity=position_quantity,
                        price=candle.close_price,
                        opened_at=candle.close_time,
                        cash_balance=cash_balance,
                        position_quantity=ZERO,
                        realized_pnl=trade_pnl,
                        decision_reason=decision.reason,
                    )
                )
                position_quantity = ZERO
                entry_price = None

        last_price = candles[-1].close_price if candles else ZERO
        unrealized_pnl = ZERO
        if position_quantity > ZERO and entry_price is not None:
            unrealized_pnl = (last_price - entry_price) * position_quantity
        final_balance = cash_balance + (position_quantity * last_price)
        open_position = position_quantity > ZERO
        metrics = self._performance_metrics(
            initial_balance=initial_balance,
            final_balance=final_balance,
            realized_pnl=realized_pnl,
            closed_trades=closed_trades,
            trades=trades,
        )

        return BacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            strategy_type=strategy_type,
            initial_balance=initial_balance,
            cash_balance=cash_balance,
            position_quantity=position_quantity,
            entry_price=entry_price,
            final_balance=final_balance,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            number_of_trades=len(trades),
            closed_trades=closed_trades,
            open_position=open_position,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            candles_processed=len(candles),
            total_return=metrics["total_return"],
            total_return_percent=metrics["total_return_percent"],
            win_rate=metrics["win_rate"],
            average_trade_pnl=metrics["average_trade_pnl"],
            best_trade_pnl=metrics["best_trade_pnl"],
            worst_trade_pnl=metrics["worst_trade_pnl"],
            profit_factor=metrics["profit_factor"],
            source=candle_source,
            trades=trades,
            decisions=decisions,
        )

    @staticmethod
    def _performance_metrics(
        *,
        initial_balance: Decimal,
        final_balance: Decimal,
        realized_pnl: Decimal,
        closed_trades: int,
        trades: list[BacktestTrade],
    ) -> dict[str, Decimal | None]:
        total_return = final_balance - initial_balance
        total_return_percent = None
        if initial_balance > ZERO:
            total_return_percent = (total_return / initial_balance) * HUNDRED

        closed_trade_pnls = [trade.realized_pnl for trade in trades if trade.side == "sell"]
        if closed_trades == 0 or not closed_trade_pnls:
            return {
                "total_return": total_return,
                "total_return_percent": total_return_percent,
                "win_rate": None,
                "average_trade_pnl": None,
                "best_trade_pnl": None,
                "worst_trade_pnl": None,
                "profit_factor": None,
            }

        winning_pnls = [pnl for pnl in closed_trade_pnls if pnl > ZERO]
        losing_pnls = [pnl for pnl in closed_trade_pnls if pnl < ZERO]
        gross_winning_pnl = sum(winning_pnls, ZERO)
        gross_losing_pnl = abs(sum(losing_pnls, ZERO))
        profit_factor = None
        if gross_losing_pnl > ZERO and gross_winning_pnl > ZERO:
            profit_factor = gross_winning_pnl / gross_losing_pnl
        elif gross_losing_pnl > ZERO:
            profit_factor = ZERO
        elif gross_winning_pnl == ZERO:
            profit_factor = ZERO

        return {
            "total_return": total_return,
            "total_return_percent": total_return_percent,
            "win_rate": (Decimal(len(winning_pnls)) / Decimal(closed_trades)) * HUNDRED,
            "average_trade_pnl": realized_pnl / Decimal(closed_trades),
            "best_trade_pnl": max(closed_trade_pnls),
            "worst_trade_pnl": min(closed_trade_pnls),
            "profit_factor": profit_factor,
        }

    @staticmethod
    def _strategy_candle_source(parameters: dict[str, Any] | None) -> str | None:
        if not parameters:
            return None
        source = parameters.get("candle_source") or parameters.get("source")
        if source is None:
            return None
        normalized = str(source).strip()
        return normalized or None
