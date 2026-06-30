import argparse
import json
import os
import sys
from pathlib import Path
from typing import TextIO

from app.cli.run_backtest import CliArgumentError, SafeArgumentParser
from app.services.backtest_comparison_report import (
    BacktestComparisonReportError,
    build_backtest_comparison_markdown_report,
    build_backtest_comparison_report,
    load_comparison_json,
)
from app.services.backtest_run_comparison import BacktestRunComparisonError, compare_backtest_run_dirs_many


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        _validate_args(args)
        comparison = _comparison_from_args(args)
        artifact_root = args.artifact_root or _default_artifact_root(args.run_dir)
        report = build_backtest_comparison_report(
            comparison,
            generated_at=args.generated_at,
            artifact_root=artifact_root,
        )
        output_json = Path(args.output_json)
        _write_text(output_json, json.dumps(report, sort_keys=True) + "\n", overwrite=args.overwrite)

        output_md = None
        if args.output_md is not None:
            output_md = Path(args.output_md)
            markdown = build_backtest_comparison_markdown_report(report, title=args.title)
            _write_text(output_md, markdown, overwrite=args.overwrite)

        print(
            json.dumps(
                {
                    "result": "PASS",
                    "output_json": str(output_json),
                    "output_md": str(output_md) if output_md is not None else None,
                    "run_count": report["run_count"],
                },
                sort_keys=True,
            ),
            file=stdout,
        )
        return 0
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (BacktestComparisonReportError, BacktestRunComparisonError, OSError, ValueError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="export-backtest-comparison-report",
        description=(
            "Export a portfolio-friendly report from saved local backtest comparison artifacts. "
            "File-based only; does not contact exchanges or touch runtime execution records."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--comparison-json", help="existing multi-run comparison JSON")
    source.add_argument("--run-dir", action="append", help="saved run directory; pass two or more times")
    parser.add_argument("--output-json", required=True, help="JSON report output path")
    parser.add_argument("--output-md", help="optional Markdown report output path")
    parser.add_argument("--artifact-root", help="root used to render safe relative run paths")
    parser.add_argument("--generated-at", help="optional generated_at timestamp for deterministic output")
    parser.add_argument("--title", default="Backtest Comparison Report", help="Markdown report title")
    parser.add_argument("--overwrite", action="store_true", help="replace existing report files")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.run_dir and len(args.run_dir) < 2:
        raise CliArgumentError("--run-dir must be passed at least twice")


def _comparison_from_args(args: argparse.Namespace) -> dict:
    if args.comparison_json is not None:
        return load_comparison_json(args.comparison_json)
    return compare_backtest_run_dirs_many(args.run_dir)


def _default_artifact_root(run_dirs: list[str] | None) -> str | None:
    if not run_dirs:
        return None
    parent_paths = [str(Path(run_dir).resolve().parent) for run_dir in run_dirs]
    return os.path.commonpath(parent_paths)


def _write_text(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise BacktestComparisonReportError(f"output file already exists; pass --overwrite to replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
