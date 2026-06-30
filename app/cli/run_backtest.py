import argparse
import csv
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TextIO

from app.services.csv_backtest import BacktestCsvError, load_candles_from_csv, run_csv_backtest

PRICE_THRESHOLD_STRATEGY_TYPE = "price_threshold"
MOVING_AVERAGE_CROSSOVER_STRATEGY_TYPE = "moving_average_crossover"


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
            parameters=_strategy_parameters_from_args(args),
        )
        full_payload = _to_jsonable(result)
        summary_payload = _summary_payload(full_payload)
        summary_payload.update(_strategy_summary_fields(args))
        if args.output_dir is not None:
            _write_output_dir(Path(args.output_dir), full_payload, summary_payload, overwrite=args.overwrite)
        output_payload = summary_payload if args.summary_only else full_payload
        output = json.dumps(output_payload, sort_keys=True)
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
    parser.add_argument("--strategy-type", required=True)
    parser.add_argument("--entry-below", help="price_threshold BUY threshold")
    parser.add_argument("--exit-above", help="price_threshold SELL threshold")
    parser.add_argument("--fast-window", help="moving_average_crossover fast moving-average window")
    parser.add_argument("--slow-window", help="moving_average_crossover slow moving-average window")
    parser.add_argument("--order-quantity", required=True, help="base quantity per BUY")
    parser.add_argument("--output-json", help="optional file path to write the full JSON result")
    parser.add_argument("--output-dir", help="optional directory for summary.json, trades.csv, and equity_curve.csv")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="print compact summary JSON to stdout instead of full trades and equity curve",
    )
    parser.add_argument("--overwrite", action="store_true", help="allow replacing files in --output-dir")
    return parser


def _strategy_parameters_from_args(args: Any) -> dict[str, Any]:
    quantity = _positive_decimal_arg(args.order_quantity, "order-quantity")
    if args.strategy_type == PRICE_THRESHOLD_STRATEGY_TYPE:
        if args.entry_below is None:
            raise ValueError("entry-below is required for price_threshold")
        if args.exit_above is None:
            raise ValueError("exit-above is required for price_threshold")
        return {
            "buy_below": _decimal_arg(args.entry_below, "entry-below"),
            "sell_above": _decimal_arg(args.exit_above, "exit-above"),
            "quantity": quantity,
        }
    if args.strategy_type == MOVING_AVERAGE_CROSSOVER_STRATEGY_TYPE:
        if args.fast_window is None:
            raise ValueError("fast-window is required for moving_average_crossover")
        if args.slow_window is None:
            raise ValueError("slow-window is required for moving_average_crossover")
        return {
            "fast_window": _positive_int_arg(args.fast_window, "fast-window"),
            "slow_window": _positive_int_arg(args.slow_window, "slow-window"),
            "quantity": quantity,
        }
    raise ValueError(f"unsupported strategy type: {args.strategy_type}")


def _strategy_summary_fields(args: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "strategy_type": args.strategy_type,
        "order_quantity": args.order_quantity,
    }
    if args.strategy_type == PRICE_THRESHOLD_STRATEGY_TYPE:
        fields["entry_below"] = args.entry_below
        fields["exit_above"] = args.exit_above
    elif args.strategy_type == MOVING_AVERAGE_CROSSOVER_STRATEGY_TYPE:
        fields["fast_window"] = args.fast_window
        fields["slow_window"] = args.slow_window
    return fields


def _decimal_arg(value: str, name: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a decimal") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    return parsed


def _positive_decimal_arg(value: str, name: str) -> Decimal:
    parsed = _decimal_arg(value, name)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _positive_int_arg(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if str(value).strip() != str(parsed):
        raise ValueError(f"{name} must be a positive integer")
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in {"trades", "equity_curve"}}


def _write_output_dir(
    output_dir: Path,
    full_payload: dict[str, Any],
    summary_payload: dict[str, Any],
    *,
    overwrite: bool,
) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"output-dir points to a file: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "summary.json"
    trades_path = output_dir / "trades.csv"
    equity_curve_path = output_dir / "equity_curve.csv"
    paths = (summary_path, trades_path, equity_curve_path)
    existing = [path.name for path in paths if path.exists()]
    if existing and not overwrite:
        raise ValueError(
            "output files already exist; pass --overwrite to replace: "
            + ", ".join(existing)
        )

    summary_path.write_text(json.dumps(summary_payload, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(
        trades_path,
        rows=full_payload["trades"],
        fieldnames=[
            "timestamp",
            "side",
            "price",
            "quantity",
            "fee",
            "cash_balance_after",
            "position_quantity_after",
            "realized_pnl",
        ],
    )
    _write_csv(
        equity_curve_path,
        rows=full_payload["equity_curve"],
        fieldnames=[
            "timestamp",
            "cash_balance",
            "position_quantity",
            "close_price",
            "equity",
            "drawdown_amount",
            "drawdown_pct",
        ],
    )


def _write_csv(path: Path, *, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


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
