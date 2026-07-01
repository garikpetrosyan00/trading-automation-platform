import json
import sys
from pathlib import Path
from typing import Any, TextIO

from app.cli.run_backtest import CliArgumentError, SafeArgumentParser
from app.cli.run_portfolio_backtest_comparison_smoke import (
    DEFAULT_CSV,
    PortfolioBacktestComparisonSmokeError,
    _demo_configs,
    _prepare_output_dir,
    _run_demo_backtest,
)
from app.services.backtest_comparison_report import (
    SAFETY_NOTE,
    BacktestComparisonReportError,
    build_backtest_comparison_markdown_report,
    build_backtest_comparison_report,
)
from app.services.backtest_comparison_report_validation import (
    BacktestComparisonReportValidationError,
    load_report_json,
    validate_backtest_comparison_report,
)
from app.services.backtest_run_comparison import BacktestRunComparisonError, compare_backtest_run_dirs_many
from app.services.csv_backtest import BacktestCsvError, load_candles_from_csv


class PortfolioBacktestReportDemoError(ValueError):
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
        run_dirs = [output_dir / summary["run_name"] for summary in run_summaries]
        comparison = compare_backtest_run_dirs_many(run_dirs)

        comparison_path = output_dir / "comparison.json"
        _write_json(comparison_path, comparison, overwrite=True)

        report_json_path = output_dir / "comparison_report.json"
        report_md_path = Path(args.output_md) if args.output_md is not None else None
        report = build_backtest_comparison_report(
            comparison,
            generated_at=args.generated_at,
            artifact_root=output_dir,
            output_json_path=report_json_path,
            output_md_path=report_md_path,
        )
        _write_json(report_json_path, report, overwrite=True)

        if report_md_path is not None:
            _write_text(
                report_md_path,
                build_backtest_comparison_markdown_report(report),
                overwrite=args.overwrite,
            )

        validation = validate_backtest_comparison_report(load_report_json(report_json_path))
        payload = _payload(
            output_dir=output_dir,
            run_summaries=run_summaries,
            comparison_path=comparison_path,
            report_json_path=report_json_path,
            report_md_path=report_md_path,
            report=report,
            validation=validation,
        )
        print(json.dumps(payload, sort_keys=True), file=stdout)
        return 0 if validation["valid"] else 1
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (
        BacktestComparisonReportError,
        BacktestComparisonReportValidationError,
        BacktestCsvError,
        BacktestRunComparisonError,
        PortfolioBacktestComparisonSmokeError,
        PortfolioBacktestReportDemoError,
        OSError,
        ValueError,
    ) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        prog="run-portfolio-backtest-report-demo",
        description=(
            "Run a local CSV portfolio backtest report demo: create artifacts, compare them, "
            "export a report, and validate it. File-based only; does not contact exchanges "
            "or touch runtime execution records."
        ),
    )
    parser.add_argument("--output-dir", required=True, help="directory for generated run artifacts and reports")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="prepared/local candle CSV path")
    parser.add_argument("--symbol", default="BTCUSDT", help="trading symbol")
    parser.add_argument("--timeframe", default="1h", help="candle timeframe label")
    parser.add_argument("--initial-balance", default="10000", help="starting quote balance")
    parser.add_argument("--fee-rate", default="0.001", help="decimal fee rate per trade")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing non-empty output directory")
    parser.add_argument("--output-md", help="optional Markdown report output path")
    parser.add_argument("--generated-at", help="optional generated_at timestamp for deterministic output")
    return parser


def _write_json(path: Path, payload: dict[str, Any], *, overwrite: bool) -> None:
    _write_text(path, json.dumps(payload, sort_keys=True) + "\n", overwrite=overwrite)


def _write_text(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise PortfolioBacktestReportDemoError(f"output file already exists; pass --overwrite to replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _payload(
    *,
    output_dir: Path,
    run_summaries: list[dict[str, Any]],
    comparison_path: Path,
    report_json_path: Path,
    report_md_path: Path | None,
    report: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "result": "PASS" if validation["valid"] else "FAIL",
        "output_dir": str(output_dir),
        "run_count": report["run_count"],
        "artifacts": {
            "runs": [
                {
                    "run_name": summary["run_name"],
                    "run_dir": str(output_dir / summary["run_name"]),
                    "summary_path": str(output_dir / summary["run_name"] / "summary.json"),
                    "trades_path": str(output_dir / summary["run_name"] / "trades.csv"),
                    "equity_curve_path": str(output_dir / summary["run_name"] / "equity_curve.csv"),
                }
                for summary in run_summaries
            ],
            "comparison_json": str(comparison_path),
            "report_json": str(report_json_path),
            "report_md": str(report_md_path) if report_md_path is not None else None,
        },
        "rankings": _ranking_summary(report.get("rankings", {})),
        "diagnostics": _diagnostics_summary(report.get("runs", [])),
        "validation": validation,
        "safety_note": SAFETY_NOTE,
    }


def _ranking_summary(rankings: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(rankings, dict):
        return {}
    return {
        metric: [
            {
                "rank": item.get("rank"),
                "run_name": item.get("run_name"),
                "run_path": item.get("run_path"),
                "value": item.get("value"),
                "available": item.get("available"),
            }
            for item in items
            if isinstance(item, dict)
        ]
        for metric, items in rankings.items()
        if isinstance(items, list)
    }


def _diagnostics_summary(runs: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(runs, list):
        return {}
    fields = (
        "completed_round_trips",
        "win_count",
        "loss_count",
        "breakeven_count",
        "average_winning_trade_pnl",
        "average_losing_trade_pnl",
        "average_trade_pnl",
        "best_trade_pnl",
        "worst_trade_pnl",
        "profit_factor",
        "max_drawdown_amount",
        "max_drawdown_pct",
        "exposure_pct",
    )
    payload: dict[str, dict[str, Any]] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        run_name = run.get("run_name")
        summary = run.get("summary")
        if isinstance(run_name, str) and isinstance(summary, dict):
            payload[run_name] = {field: summary.get(field) for field in fields if field in summary}
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
