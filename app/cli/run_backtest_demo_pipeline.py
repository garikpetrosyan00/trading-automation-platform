import json
import shutil
import sys
from pathlib import Path
from typing import Any, TextIO

from app.cli.run_backtest import (
    CliArgumentError,
    SafeArgumentParser,
    _decimal_arg,
    _positive_decimal_arg,
    _summary_payload,
    _to_jsonable,
    _write_output_dir,
)
from app.services.backtest_dataset import (
    DatasetPreparationError,
    prepare_backtest_dataset,
    summary_to_jsonable,
)
from app.services.backtest_demo_bundle import BacktestDemoBundleError, export_backtest_demo_bundle
from app.services.backtest_report import BacktestReportError, build_backtest_markdown_report
from app.services.backtest_run_comparison import (
    BacktestRunComparisonError,
    compact_backtest_comparison_report,
    compare_backtest_run_dirs,
    compare_backtest_summaries,
)
from app.services.csv_backtest import BacktestCsvError, load_candles_from_csv, run_csv_backtest


class BacktestDemoPipelineError(ValueError):
    pass


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        work_dir = Path(args.work_dir)
        _prepare_work_dir(work_dir, overwrite=args.overwrite)

        paths = _pipeline_paths(work_dir)
        dataset_summary = _prepare_or_copy_dataset(args, paths["prepared_csv"], paths["dataset_summary"])
        run_summary = _run_backtest(args, paths["prepared_csv"], paths["run_dir"])
        comparison_report = _maybe_compare(args, paths["run_dir"], paths["run_summary"], paths["comparison_json"])
        _write_report(args, paths["run_dir"], paths["comparison_json"] if comparison_report is not None else None, paths["report_md"])
        manifest = export_backtest_demo_bundle(
            run_dir=paths["run_dir"],
            comparison_json=paths["comparison_json"] if comparison_report is not None else None,
            report_md=paths["report_md"],
            output_dir=paths["bundle_dir"],
            title=args.title or "Backtest Demo Bundle",
            overwrite=True,
        )

        payload = _result_payload(
            work_dir=work_dir,
            paths=paths,
            dataset_summary=dataset_summary,
            run_summary=run_summary,
            comparison_report=comparison_report,
            manifest=manifest,
            compact=args.compact,
        )
        print(json.dumps(payload, sort_keys=True), file=stdout)
        return 0
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (
        BacktestCsvError,
        BacktestDemoBundleError,
        BacktestDemoPipelineError,
        BacktestReportError,
        BacktestRunComparisonError,
        DatasetPreparationError,
        OSError,
        ValueError,
    ) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        prog="run-backtest-demo-pipeline",
        description=(
            "Run the local CSV backtest demo pipeline: prepare/copy dataset, run backtest, "
            "optionally compare, export report, and package a demo bundle. File-based only."
        ),
    )
    parser.add_argument("--symbol", required=True, help="trading symbol, for example BTCUSDT")
    parser.add_argument("--timeframe", required=True, help="candle timeframe label, for example 1h")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", action="append", help="raw candle CSV input path; repeatable")
    source.add_argument("--prepared-csv", help="existing prepared candle CSV path")
    parser.add_argument("--work-dir", required=True, help="pipeline output work directory")
    parser.add_argument("--initial-balance", required=True, help="starting quote balance")
    parser.add_argument("--fee-rate", required=True, help="decimal fee rate per trade, for example 0.001")
    parser.add_argument("--strategy-type", required=True)
    parser.add_argument("--entry-below", required=True, help="price_threshold BUY threshold")
    parser.add_argument("--exit-above", required=True, help="price_threshold SELL threshold")
    parser.add_argument("--order-quantity", required=True, help="base quantity per BUY")
    parser.add_argument("--compare-summary", help="optional previous summary.json path")
    parser.add_argument("--base-run-dir", help="optional previous run directory containing summary.json")
    parser.add_argument("--title", help="optional report and bundle title")
    parser.add_argument("--dedupe", choices=["keep-first", "keep-last"], help="handle duplicate raw timestamps")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing non-empty work directory")
    parser.add_argument("--compact", action="store_true", help="print compact artifact paths only")
    return parser


def _prepare_work_dir(work_dir: Path, *, overwrite: bool) -> None:
    if work_dir.exists() and not work_dir.is_dir():
        raise BacktestDemoPipelineError(f"work-dir points to a file: {work_dir}")
    if work_dir.exists() and any(work_dir.iterdir()):
        if not overwrite:
            raise BacktestDemoPipelineError(f"work directory is not empty; pass --overwrite to replace: {work_dir}")
        for child in work_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    work_dir.mkdir(parents=True, exist_ok=True)


def _pipeline_paths(work_dir: Path) -> dict[str, Path]:
    return {
        "dataset_dir": work_dir / "dataset",
        "prepared_csv": work_dir / "dataset" / "prepared.csv",
        "dataset_summary": work_dir / "dataset" / "summary.json",
        "run_dir": work_dir / "run",
        "run_summary": work_dir / "run" / "summary.json",
        "trades_csv": work_dir / "run" / "trades.csv",
        "equity_curve_csv": work_dir / "run" / "equity_curve.csv",
        "comparison_json": work_dir / "comparison.json",
        "report_md": work_dir / "report.md",
        "bundle_dir": work_dir / "bundle",
    }


def _prepare_or_copy_dataset(args: Any, prepared_csv: Path, dataset_summary_path: Path) -> dict[str, Any]:
    prepared_csv.parent.mkdir(parents=True, exist_ok=True)
    if args.prepared_csv is not None:
        source = Path(args.prepared_csv)
        if not source.exists():
            raise BacktestDemoPipelineError(f"prepared CSV does not exist: {source}")
        if not source.is_file():
            raise BacktestDemoPipelineError(f"prepared CSV path is not a file: {source}")
        if source.resolve() != prepared_csv.resolve():
            shutil.copyfile(source, prepared_csv)
        summary: dict[str, Any] = {
            "symbol": args.symbol.strip().upper(),
            "timeframe": args.timeframe.strip(),
            "prepared": False,
            "source_prepared_csv": str(source),
            "output_path": str(prepared_csv),
        }
    else:
        prepared = prepare_backtest_dataset(
            input_paths=args.input,
            output_path=prepared_csv,
            symbol=args.symbol,
            timeframe=args.timeframe,
            dedupe=args.dedupe,
            overwrite=True,
        )
        summary = summary_to_jsonable(prepared)
        summary["prepared"] = True
    dataset_summary_path.write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _run_backtest(args: Any, prepared_csv: Path, run_dir: Path) -> dict[str, Any]:
    result = run_csv_backtest(
        candles=load_candles_from_csv(prepared_csv),
        symbol=args.symbol,
        timeframe=args.timeframe,
        initial_balance=_decimal_arg(args.initial_balance, "initial-balance"),
        fee_rate=_decimal_arg(args.fee_rate, "fee-rate"),
        strategy_type=args.strategy_type,
        parameters={
            "buy_below": _decimal_arg(args.entry_below, "entry-below"),
            "sell_above": _decimal_arg(args.exit_above, "exit-above"),
            "quantity": _positive_decimal_arg(args.order_quantity, "order-quantity"),
        },
    )
    full_payload = _to_jsonable(result)
    summary_payload = _summary_payload(full_payload)
    summary_payload.update(
        {
            "prepared_csv": str(prepared_csv),
            "strategy_type": args.strategy_type,
            "initial_balance": args.initial_balance,
            "fee_rate": args.fee_rate,
            "entry_below": args.entry_below,
            "exit_above": args.exit_above,
            "order_quantity": args.order_quantity,
        }
    )
    _write_output_dir(run_dir, full_payload, summary_payload, overwrite=True)
    return summary_payload


def _maybe_compare(args: Any, run_dir: Path, run_summary: Path, comparison_json: Path) -> dict[str, Any] | None:
    if args.base_run_dir is not None and args.compare_summary is not None:
        raise BacktestDemoPipelineError("pass only one of --base-run-dir or --compare-summary")
    if args.base_run_dir is not None:
        report = compare_backtest_run_dirs(args.base_run_dir, run_dir)
    elif args.compare_summary is not None:
        report = compare_backtest_summaries(
            base_summary_path=args.compare_summary,
            candidate_summary_path=run_summary,
        )
    else:
        return None
    comparison_json.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _write_report(args: Any, run_dir: Path, comparison_json: Path | None, report_md: Path) -> None:
    markdown = build_backtest_markdown_report(
        run_dir=run_dir,
        comparison_json=comparison_json,
        title=args.title or "Backtest Demo Report",
    )
    report_md.write_text(markdown, encoding="utf-8")


def _result_payload(
    *,
    work_dir: Path,
    paths: dict[str, Path],
    dataset_summary: dict[str, Any],
    run_summary: dict[str, Any],
    comparison_report: dict[str, Any] | None,
    manifest: dict[str, Any],
    compact: bool,
) -> dict[str, Any]:
    artifact_paths = {
        "work_dir": str(work_dir),
        "prepared_csv": str(paths["prepared_csv"]),
        "dataset_summary": str(paths["dataset_summary"]),
        "run_dir": str(paths["run_dir"]),
        "run_summary": str(paths["run_summary"]),
        "trades_csv": str(paths["trades_csv"]),
        "equity_curve_csv": str(paths["equity_curve_csv"]),
        "comparison_json": str(paths["comparison_json"]) if comparison_report is not None else None,
        "report_md": str(paths["report_md"]),
        "bundle_dir": str(paths["bundle_dir"]),
        "bundle_manifest": str(paths["bundle_dir"] / "manifest.json"),
    }
    payload: dict[str, Any] = {
        "result": "PASS",
        "artifacts": artifact_paths,
        "comparison_created": comparison_report is not None,
    }
    if not compact:
        payload["dataset"] = dataset_summary
        payload["run"] = {
            "final_equity": run_summary.get("final_equity"),
            "total_return_pct": run_summary.get("total_return_pct"),
            "trades_count": run_summary.get("trades_count"),
        }
        payload["bundle"] = {
            "files_count": len(manifest["files"]),
            "comparison_included": manifest["comparison_included"],
            "report_included": manifest["report_included"],
        }
        if comparison_report is not None:
            payload["comparison"] = compact_backtest_comparison_report(comparison_report)
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
