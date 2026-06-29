import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from app.cli.run_backtest import CliArgumentError, SafeArgumentParser
from app.services.backtest_report import BacktestReportError, build_backtest_markdown_report


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        markdown = build_backtest_markdown_report(
            run_dir=args.run_dir,
            comparison_json=args.comparison_json,
            title=args.title,
        )
        output_path = Path(args.output_md)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "run_dir": str(Path(args.run_dir)),
                    "output_md": str(output_path),
                    "comparison_json": str(Path(args.comparison_json)) if args.comparison_json is not None else None,
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
    except (BacktestReportError, OSError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="export-backtest-report",
        description=(
            "Export a Markdown report from saved local CSV backtest artifacts. File-based only; "
            "does not contact exchanges or touch runtime execution records."
        ),
    )
    parser.add_argument("--run-dir", required=True, help="saved run directory containing summary.json")
    parser.add_argument("--comparison-json", help="optional comparison JSON from compare-backtest-runs")
    parser.add_argument("--output-md", required=True, help="Markdown report output path")
    parser.add_argument("--title", help="optional report title")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
