import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TextIO

from app.services.csv_backtest import BacktestCsvError, load_candles_from_csv, run_csv_backtest


class CliArgumentError(Exception):
    pass


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(message)


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        result = run_csv_backtest(
            candles=load_candles_from_csv(args.csv),
            symbol=args.symbol,
            timeframe=args.timeframe,
            initial_balance=_decimal_arg(args.initial_balance, "initial-balance"),
            fee_rate=_decimal_arg(args.fee_rate, "fee-rate"),
            strategy_type=args.strategy_type,
            parameters={
                "buy_below": _decimal_arg(args.entry_below, "entry-below"),
                "sell_above": _decimal_arg(args.exit_above, "exit-above"),
                "quantity": _decimal_arg(args.order_quantity, "order-quantity"),
            },
        )
        payload = _to_jsonable(result)
        output = json.dumps(payload, sort_keys=True)
        if args.output_json is not None:
            Path(args.output_json).write_text(output + "\n", encoding="utf-8")
        print(output, file=stdout)
        return 0
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (BacktestCsvError, ValueError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="run-backtest",
        description="Run a local CSV backtest. Pure simulation only; does not create runtime orders or contact exchanges.",
    )
    parser.add_argument("--symbol", required=True, help="trading symbol, for example BTCUSDT")
    parser.add_argument("--timeframe", required=True, help="candle timeframe label, for example 1h")
    parser.add_argument("--csv", required=True, help="path to historical candle CSV")
    parser.add_argument("--initial-balance", required=True, help="starting quote balance")
    parser.add_argument("--fee-rate", required=True, help="decimal fee rate per trade, for example 0.001")
    parser.add_argument("--strategy-type", required=True, choices=["price_threshold"])
    parser.add_argument("--entry-below", required=True, help="price_threshold BUY threshold")
    parser.add_argument("--exit-above", required=True, help="price_threshold SELL threshold")
    parser.add_argument("--order-quantity", required=True, help="base quantity per BUY")
    parser.add_argument("--output-json", help="optional file path to write the full JSON result")
    return parser


def _decimal_arg(value: str, name: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a decimal") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    return parsed


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
