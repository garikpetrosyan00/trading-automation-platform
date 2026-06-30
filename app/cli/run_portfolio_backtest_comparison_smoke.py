import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, TextIO

from app.cli.run_backtest import (
    CliArgumentError,
    SafeArgumentParser,
    _decimal_arg,
    _summary_payload,
    _to_jsonable,
    _write_output_dir,
)
from app.services.backtest_run_comparison import BacktestRunComparisonError, compare_backtest_run_dirs_many
from app.services.csv_backtest import BacktestCsvError, load_candles_from_csv, run_csv_backtest


DEFAULT_CSV = Path("data/backtests/BTCUSDT_1h_sample.csv")


class PortfolioBacktestComparisonSmokeError(ValueError):
    pass


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        output_dir = Path(args.output_dir)
        _prepare_output_dir(output_dir, overwrite=args.overwrite)

        candles = load_candles_from_csv(args.csv)
        run_summaries = [
            _run_demo_backtest(args, candles, output_dir, config)
            for config in _demo_configs()
        ]
        comparison = compare_backtest_run_dirs_many([output_dir / summary["run_name"] for summary in run_summaries])
        payload = _payload(output_dir=output_dir, run_summaries=run_summaries, comparison=comparison)
        print(json.dumps(payload, sort_keys=True), file=stdout)
        return 0
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (BacktestCsvError, BacktestRunComparisonError, PortfolioBacktestComparisonSmokeError, OSError, ValueError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        prog="run-portfolio-backtest-comparison-smoke",
        description=(
            "Create deterministic local CSV backtest artifacts and compare them. "
            "File-based only; does not contact exchanges or create runtime execution records."
        ),
    )
    parser.add_argument("--output-dir", required=True, help="directory for generated local backtest run artifacts")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="prepared/local candle CSV path")
    parser.add_argument("--symbol", default="BTCUSDT", help="trading symbol")
    parser.add_argument("--timeframe", default="1h", help="candle timeframe label")
    parser.add_argument("--initial-balance", default="10000", help="starting quote balance")
    parser.add_argument("--fee-rate", default="0.001", help="decimal fee rate per trade")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing non-empty output directory")
    return parser


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise PortfolioBacktestComparisonSmokeError(f"output-dir points to a file: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise PortfolioBacktestComparisonSmokeError(
                f"output directory is not empty; pass --overwrite to replace: {output_dir}"
            )
        for child in output_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)


def _demo_configs() -> list[dict[str, Any]]:
    return [
        {
            "run_name": "base_price_threshold",
            "entry_below": Decimal("95000"),
            "exit_above": Decimal("105000"),
            "order_quantity": Decimal("0.01"),
        },
        {
            "run_name": "candidate_price_threshold",
            "entry_below": Decimal("96000"),
            "exit_above": Decimal("99000"),
            "order_quantity": Decimal("0.01"),
        },
    ]


def _run_demo_backtest(args: Any, candles: list[Any], output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    result = run_csv_backtest(
        candles=candles,
        symbol=args.symbol,
        timeframe=args.timeframe,
        initial_balance=_decimal_arg(args.initial_balance, "initial-balance"),
        fee_rate=_decimal_arg(args.fee_rate, "fee-rate"),
        strategy_type="price_threshold",
        parameters={
            "buy_below": config["entry_below"],
            "sell_above": config["exit_above"],
            "quantity": config["order_quantity"],
        },
    )
    full_payload = _to_jsonable(result)
    summary_payload = _summary_payload(full_payload)
    summary_payload.update(
        {
            "run_name": config["run_name"],
            "strategy_type": "price_threshold",
            "entry_below": _decimal_to_string(config["entry_below"]),
            "exit_above": _decimal_to_string(config["exit_above"]),
            "order_quantity": _decimal_to_string(config["order_quantity"]),
            "initial_balance": args.initial_balance,
            "fee_rate": args.fee_rate,
            "prepared_csv": str(Path(args.csv)),
        }
    )
    run_dir = output_dir / config["run_name"]
    summary_payload["output_dir"] = str(run_dir)
    _write_output_dir(run_dir, full_payload, summary_payload, overwrite=True)
    return summary_payload


def _payload(*, output_dir: Path, run_summaries: list[dict[str, Any]], comparison: dict[str, Any]) -> dict[str, Any]:
    return {
        "result": "PASS",
        "output_dir": str(output_dir),
        "runs_count": len(run_summaries),
        "runs": [
            {
                "run_name": summary["run_name"],
                "run_dir": str(output_dir / summary["run_name"]),
                "summary_path": str(output_dir / summary["run_name"] / "summary.json"),
                "summary": _portfolio_summary(summary),
            }
            for summary in run_summaries
        ],
        "comparison": comparison,
        "safety_note": (
            "Local CSV artifact comparison only; no live/testnet/Binance calls, DB writes, "
            "orders, fills, execution attempts, reconciliation jobs, or paper/live execution."
        ),
    }


def _portfolio_summary(summary: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "strategy_type",
        "entry_below",
        "exit_above",
        "order_quantity",
        "starting_balance",
        "ending_balance",
        "total_return",
        "total_return_pct",
        "realized_pnl",
        "trades_count",
        "completed_round_trips",
        "win_count",
        "loss_count",
        "win_rate_pct",
        "max_drawdown_pct",
    ]
    return {field: summary.get(field) for field in fields if field in summary}


def _decimal_to_string(value: Decimal) -> str:
    return format(value.normalize(), "f")


if __name__ == "__main__":
    raise SystemExit(main())
