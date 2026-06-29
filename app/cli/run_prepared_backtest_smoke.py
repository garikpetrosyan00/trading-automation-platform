import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TextIO

from app.cli.run_backtest import (
    CliArgumentError,
    SafeArgumentParser,
    _decimal_arg,
    _summary_payload,
    _strategy_parameters_from_args,
    _strategy_summary_fields,
    _to_jsonable,
    _write_output_dir,
)
from app.services.csv_backtest import BacktestCsvError, load_candles_from_csv, run_csv_backtest


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
            parameters=_strategy_parameters_from_args(args),
        )
        full_payload = _to_jsonable(result)
        summary_payload = _summary_payload(full_payload)
        summary_payload.update(_strategy_summary_fields(args))
        summary_payload["prepared_csv"] = str(Path(args.csv))
        if args.compare_summary is not None:
            summary_payload["comparison"] = _compare_summary(Path(args.compare_summary), summary_payload)
        if args.output_dir is not None:
            summary_payload["output_dir"] = str(Path(args.output_dir))
            _write_output_dir(Path(args.output_dir), full_payload, summary_payload, overwrite=args.overwrite)
        print(json.dumps(summary_payload, sort_keys=True), file=stdout)
        return 0
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (BacktestCsvError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="run-prepared-backtest-smoke",
        description=(
            "Run a local prepared CSV backtest smoke. Pure file-based simulation only; "
            "does not contact exchanges or create runtime execution records."
        ),
    )
    parser.add_argument("--symbol", required=True, help="trading symbol, for example BTCUSDT")
    parser.add_argument("--timeframe", required=True, help="candle timeframe label, for example 1h")
    parser.add_argument("--csv", required=True, help="path to prepared candle CSV")
    parser.add_argument("--initial-balance", required=True, help="starting quote balance")
    parser.add_argument("--fee-rate", required=True, help="decimal fee rate per trade, for example 0.001")
    parser.add_argument("--strategy-type", required=True)
    parser.add_argument("--entry-below", help="price_threshold BUY threshold")
    parser.add_argument("--exit-above", help="price_threshold SELL threshold")
    parser.add_argument("--fast-window", help="moving_average_crossover fast moving-average window")
    parser.add_argument("--slow-window", help="moving_average_crossover slow moving-average window")
    parser.add_argument("--order-quantity", required=True, help="base quantity per BUY")
    parser.add_argument("--output-dir", help="optional directory for summary.json, trades.csv, and equity_curve.csv")
    parser.add_argument("--overwrite", action="store_true", help="allow replacing files in --output-dir")
    parser.add_argument("--compare-summary", help="optional previous summary.json path for local result comparison")
    return parser


def _compare_summary(previous_path: Path, current_summary: dict[str, Any]) -> dict[str, Any]:
    if not previous_path.exists():
        raise ValueError(f"compare-summary file does not exist: {previous_path}")
    if not previous_path.is_file():
        raise ValueError(f"compare-summary path is not a file: {previous_path}")
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    if not isinstance(previous, dict):
        raise ValueError("compare-summary must contain a JSON object")

    return {
        "previous_summary_path": str(previous_path),
        "final_equity_delta": _decimal_delta(current_summary, previous, "final_equity"),
        "total_return_pct_delta": _decimal_delta(current_summary, previous, "total_return_pct"),
        "max_drawdown_pct_delta": _decimal_delta(current_summary, previous, "max_drawdown_pct"),
        "trades_count_delta": int(current_summary.get("trades_count", 0)) - int(previous.get("trades_count", 0)),
    }


def _decimal_delta(current: dict[str, Any], previous: dict[str, Any], key: str) -> str:
    try:
        delta = Decimal(str(current[key])) - Decimal(str(previous[key]))
    except (KeyError, InvalidOperation, ValueError) as exc:
        raise ValueError(f"compare-summary missing or invalid decimal field: {key}") from exc
    return format(delta.normalize(), "f")


if __name__ == "__main__":
    raise SystemExit(main())
