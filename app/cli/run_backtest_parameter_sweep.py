import json
import sys
from decimal import Decimal
from typing import TextIO

from app.cli.run_backtest import CliArgumentError, SafeArgumentParser, _decimal_arg, _positive_decimal_arg
from app.services.backtest_parameter_sweep import (
    BacktestParameterSweepError,
    compact_sweep_summary,
    run_backtest_parameter_sweep,
)
from app.services.csv_backtest import BacktestCsvError, load_candles_from_csv


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        summary = run_backtest_parameter_sweep(
            candles=load_candles_from_csv(args.csv),
            symbol=args.symbol,
            timeframe=args.timeframe,
            initial_balance=_decimal_arg(args.initial_balance, "initial-balance"),
            fee_rate=_decimal_arg(args.fee_rate, "fee-rate"),
            strategy_type=args.strategy_type,
            entry_below_values=_decimal_list_arg(args.entry_below_values, "entry-below-values"),
            exit_above_values=_decimal_list_arg(args.exit_above_values, "exit-above-values"),
            order_quantity=_positive_decimal_arg(args.order_quantity, "order-quantity"),
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
        payload = compact_sweep_summary(summary) if args.compact else summary
        print(json.dumps(payload, sort_keys=True), file=stdout)
        return 0
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (BacktestCsvError, BacktestParameterSweepError, ValueError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        prog="run-backtest-parameter-sweep",
        description=(
            "Run a local CSV backtest parameter sweep. Pure file-based simulation only; "
            "does not contact exchanges or touch runtime execution records."
        ),
    )
    parser.add_argument("--symbol", required=True, help="trading symbol, for example BTCUSDT")
    parser.add_argument("--timeframe", required=True, help="candle timeframe label, for example 1h")
    parser.add_argument("--csv", required=True, help="prepared historical candle CSV")
    parser.add_argument("--initial-balance", required=True, help="starting quote balance")
    parser.add_argument("--fee-rate", required=True, help="decimal fee rate per trade, for example 0.001")
    parser.add_argument("--strategy-type", required=True)
    parser.add_argument("--entry-below-values", required=True, help="comma-separated BUY thresholds")
    parser.add_argument("--exit-above-values", required=True, help="comma-separated SELL thresholds")
    parser.add_argument("--order-quantity", required=True, help="base quantity per BUY")
    parser.add_argument("--output-dir", required=True, help="directory for sweep outputs")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing non-empty output directory")
    parser.add_argument("--compact", action="store_true", help="print compact sweep JSON to stdout")
    return parser


def _decimal_list_arg(value: str, name: str) -> list[Decimal]:
    parts = [part.strip() for part in value.split(",")]
    if not parts or any(part == "" for part in parts):
        raise ValueError(f"{name} must be a comma-separated decimal list")
    parsed = [_decimal_arg(part, name) for part in parts]
    if any(item <= 0 for item in parsed):
        raise ValueError(f"{name} values must be positive")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
