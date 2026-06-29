from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.engine.strategy_engine import StrategyEngine

ZERO = Decimal("0")
HUNDRED = Decimal("100")
REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
PRICE_THRESHOLD_STRATEGY_TYPE = "price_threshold"
MOVING_AVERAGE_CROSSOVER_STRATEGY_TYPE = "moving_average_crossover"


class BacktestCsvError(ValueError):
    pass


@dataclass(frozen=True)
class CsvBacktestCandle:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    @property
    def close_time(self) -> datetime:
        return self.timestamp

    @property
    def close_price(self) -> Decimal:
        return self.close


@dataclass(frozen=True)
class CsvBacktestTrade:
    timestamp: datetime
    side: str
    price: Decimal
    quantity: Decimal
    fee: Decimal
    cash_balance_after: Decimal
    position_quantity_after: Decimal
    realized_pnl: Decimal | None = None


@dataclass(frozen=True)
class CsvBacktestEquityPoint:
    timestamp: datetime
    cash_balance: Decimal
    position_quantity: Decimal
    close_price: Decimal
    equity: Decimal
    drawdown_pct: Decimal


@dataclass(frozen=True)
class CsvBacktestResult:
    result: str
    symbol: str
    timeframe: str
    candles_count: int
    initial_balance: Decimal
    final_balance: Decimal
    final_position_quantity: Decimal
    final_equity: Decimal
    total_return_pct: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    trades_count: int
    buy_count: int
    sell_count: int
    win_rate_pct: Decimal | None
    fees_paid: Decimal
    max_drawdown_pct: Decimal
    buy_and_hold_return_pct: Decimal
    started_at: datetime
    ended_at: datetime
    trades: list[CsvBacktestTrade] = field(default_factory=list)
    equity_curve: list[CsvBacktestEquityPoint] = field(default_factory=list)


def load_candles_from_csv(path: str | Path) -> list[CsvBacktestCandle]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise BacktestCsvError(f"CSV file does not exist: {csv_path}")
    if not csv_path.is_file():
        raise BacktestCsvError(f"CSV path is not a file: {csv_path}")
    try:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise BacktestCsvError("CSV is empty")
            missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
            if missing:
                raise BacktestCsvError(f"CSV is missing required columns: {', '.join(missing)}")
            candles = [_parse_row(row, row_number=index) for index, row in enumerate(reader, start=2)]
    except OSError as exc:
        raise BacktestCsvError(f"CSV could not be read: {csv_path}") from exc

    if not candles:
        raise BacktestCsvError("CSV contains no candles")

    seen: set[datetime] = set()
    for candle in candles:
        if candle.timestamp in seen:
            raise BacktestCsvError(f"duplicate candle timestamp: {candle.timestamp.isoformat()}")
        seen.add(candle.timestamp)
    return sorted(candles, key=lambda candle: candle.timestamp)


def run_csv_backtest(
    *,
    candles: list[CsvBacktestCandle],
    symbol: str,
    timeframe: str,
    initial_balance: Decimal,
    fee_rate: Decimal,
    strategy_type: str,
    parameters: dict[str, Any],
) -> CsvBacktestResult:
    _validate_positive(initial_balance, "initial_balance")
    _validate_non_negative(fee_rate, "fee_rate")
    if not candles:
        raise BacktestCsvError("at least one candle is required")
    engine_strategy_type = _engine_strategy_type(strategy_type)
    if engine_strategy_type is None:
        raise BacktestCsvError(f"unsupported strategy type: {strategy_type}")
    parameters = _normalized_strategy_parameters(
        strategy_type=strategy_type,
        parameters=parameters,
        candles_count=len(candles),
    )

    cash_balance = initial_balance
    position_quantity = ZERO
    average_entry_price = ZERO
    realized_pnl = ZERO
    fees_paid = ZERO
    trades: list[CsvBacktestTrade] = []
    equity_curve: list[CsvBacktestEquityPoint] = []
    winning_sells = 0
    losing_sells = 0
    peak_equity = initial_balance
    max_drawdown_pct = ZERO
    profile = SimpleNamespace(entry_below=None, exit_above=None, order_quantity=None)

    for index, candle in enumerate(candles):
        visible_candles = candles[: index + 1]
        decision = StrategyEngine.evaluate(
            strategy_type=engine_strategy_type,
            parameters=parameters,
            profile=profile,
            latest_price=candle.close,
            position_quantity=position_quantity,
            candles=visible_candles,
        )

        if decision.decision == "buy" and position_quantity <= ZERO:
            quantity = decision.metadata.get("_order_quantity")
            if quantity is not None:
                notional = quantity * candle.close
                fee = notional * fee_rate
                total_cost = notional + fee
                if quantity > ZERO and total_cost <= cash_balance:
                    cash_balance -= total_cost
                    position_quantity = quantity
                    average_entry_price = total_cost / quantity
                    fees_paid += fee
                    trades.append(
                        CsvBacktestTrade(
                            timestamp=candle.timestamp,
                            side="buy",
                            price=candle.close,
                            quantity=quantity,
                            fee=fee,
                            cash_balance_after=cash_balance,
                            position_quantity_after=position_quantity,
                        )
                    )

        elif decision.decision == "sell" and position_quantity > ZERO:
            quantity = position_quantity
            notional = quantity * candle.close
            fee = notional * fee_rate
            net_proceeds = notional - fee
            trade_pnl = net_proceeds - (quantity * average_entry_price)
            cash_balance += net_proceeds
            position_quantity = ZERO
            average_entry_price = ZERO
            realized_pnl += trade_pnl
            fees_paid += fee
            if trade_pnl > ZERO:
                winning_sells += 1
            elif trade_pnl < ZERO:
                losing_sells += 1
            trades.append(
                CsvBacktestTrade(
                    timestamp=candle.timestamp,
                    side="sell",
                    price=candle.close,
                    quantity=quantity,
                    fee=fee,
                    cash_balance_after=cash_balance,
                    position_quantity_after=position_quantity,
                    realized_pnl=trade_pnl,
                )
            )

        equity = cash_balance + (position_quantity * candle.close)
        if equity > peak_equity:
            peak_equity = equity
        drawdown_pct = ZERO if peak_equity <= ZERO else ((peak_equity - equity) / peak_equity) * HUNDRED
        if drawdown_pct > max_drawdown_pct:
            max_drawdown_pct = drawdown_pct
        equity_curve.append(
            CsvBacktestEquityPoint(
                timestamp=candle.timestamp,
                cash_balance=cash_balance,
                position_quantity=position_quantity,
                close_price=candle.close,
                equity=equity,
                drawdown_pct=drawdown_pct,
            )
        )

    last_close = candles[-1].close
    final_equity = cash_balance + (position_quantity * last_close)
    unrealized_pnl = (
        (last_close * position_quantity) - (average_entry_price * position_quantity)
        if position_quantity > ZERO
        else ZERO
    )
    sell_count = winning_sells + losing_sells
    flat_sells = len([trade for trade in trades if trade.side == "sell"]) - sell_count
    if flat_sells:
        sell_count += flat_sells
    win_rate_pct = None if sell_count == 0 else (Decimal(winning_sells) / Decimal(sell_count)) * HUNDRED
    buy_and_hold_return_pct = ((candles[-1].close - candles[0].close) / candles[0].close) * HUNDRED

    return CsvBacktestResult(
        result="PASS",
        symbol=symbol.strip().upper(),
        timeframe=timeframe.strip(),
        candles_count=len(candles),
        initial_balance=initial_balance,
        final_balance=cash_balance,
        final_position_quantity=position_quantity,
        final_equity=final_equity,
        total_return_pct=((final_equity - initial_balance) / initial_balance) * HUNDRED,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        trades_count=len(trades),
        buy_count=len([trade for trade in trades if trade.side == "buy"]),
        sell_count=len([trade for trade in trades if trade.side == "sell"]),
        win_rate_pct=win_rate_pct,
        fees_paid=fees_paid,
        max_drawdown_pct=max_drawdown_pct,
        buy_and_hold_return_pct=buy_and_hold_return_pct,
        started_at=candles[0].timestamp,
        ended_at=candles[-1].timestamp,
        trades=trades,
        equity_curve=equity_curve,
    )


def _parse_row(row: dict[str, str], *, row_number: int) -> CsvBacktestCandle:
    timestamp = _parse_timestamp(row.get("timestamp", ""), row_number=row_number)
    open_price = _parse_decimal(row.get("open", ""), "open", row_number=row_number, positive=True)
    high_price = _parse_decimal(row.get("high", ""), "high", row_number=row_number, positive=True)
    low_price = _parse_decimal(row.get("low", ""), "low", row_number=row_number, positive=True)
    close_price = _parse_decimal(row.get("close", ""), "close", row_number=row_number, positive=True)
    volume = _parse_decimal(row.get("volume", ""), "volume", row_number=row_number, positive=False)
    if volume < ZERO:
        raise BacktestCsvError(f"row {row_number}: volume must not be negative")
    return CsvBacktestCandle(
        timestamp=timestamp,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=volume,
    )


def _engine_strategy_type(strategy_type: str) -> str | None:
    if strategy_type == PRICE_THRESHOLD_STRATEGY_TYPE:
        return PRICE_THRESHOLD_STRATEGY_TYPE
    if strategy_type == MOVING_AVERAGE_CROSSOVER_STRATEGY_TYPE:
        return "moving_average_cross"
    return None


def _normalized_strategy_parameters(
    *,
    strategy_type: str,
    parameters: dict[str, Any],
    candles_count: int,
) -> dict[str, Any]:
    if strategy_type == PRICE_THRESHOLD_STRATEGY_TYPE:
        return parameters
    if strategy_type != MOVING_AVERAGE_CROSSOVER_STRATEGY_TYPE:
        return parameters

    fast_window = _parse_positive_int_parameter(parameters.get("fast_window"), "fast_window")
    slow_window = _parse_positive_int_parameter(parameters.get("slow_window"), "slow_window")
    if fast_window >= slow_window:
        raise BacktestCsvError("fast_window must be smaller than slow_window")
    required_candles = slow_window + 1
    if candles_count < required_candles:
        raise BacktestCsvError(
            f"not enough candles for moving_average_crossover: need at least {required_candles}, got {candles_count}"
        )
    return {
        "short_window": fast_window,
        "long_window": slow_window,
        "quantity": parameters.get("quantity"),
    }


def _parse_positive_int_parameter(value: Any, name: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise BacktestCsvError(f"{name} must be a positive integer") from exc
    if str(value).strip() != str(parsed):
        raise BacktestCsvError(f"{name} must be a positive integer")
    if parsed <= 0:
        raise BacktestCsvError(f"{name} must be positive")
    return parsed


def _parse_timestamp(value: str, *, row_number: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BacktestCsvError(f"row {row_number}: timestamp is not parseable") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_decimal(value: str, name: str, *, row_number: int, positive: bool) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BacktestCsvError(f"row {row_number}: {name} must be a decimal") from exc
    if not parsed.is_finite():
        raise BacktestCsvError(f"row {row_number}: {name} must be finite")
    if positive and parsed <= ZERO:
        raise BacktestCsvError(f"row {row_number}: {name} must be positive")
    return parsed


def _validate_positive(value: Decimal, name: str) -> None:
    if not value.is_finite() or value <= ZERO:
        raise BacktestCsvError(f"{name} must be positive")


def _validate_non_negative(value: Decimal, name: str) -> None:
    if not value.is_finite() or value < ZERO:
        raise BacktestCsvError(f"{name} must not be negative")
