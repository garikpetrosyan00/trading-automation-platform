import argparse
import json
import sys
from typing import TextIO

from app.cli.run_backtest import CliArgumentError, SafeArgumentParser
from app.services.backtest_comparison_report_validation import (
    BacktestComparisonReportValidationError,
    load_report_json,
    validate_backtest_comparison_report,
)


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        report = load_report_json(args.report_json)
        result = validate_backtest_comparison_report(
            report,
            allow_absolute_paths=args.allow_absolute_paths,
        )
        print(json.dumps(result, sort_keys=True), file=stdout)
        return 0 if result["valid"] else 1
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (BacktestComparisonReportValidationError, OSError) as exc:
        print(
            json.dumps(
                {
                    "valid": False,
                    "errors": [str(exc)],
                    "warnings": [],
                    "checked_fields": [],
                },
                sort_keys=True,
            ),
            file=stdout,
        )
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="validate-backtest-comparison-report",
        description=(
            "Validate an exported local backtest comparison report. File-based only; "
            "does not contact exchanges or touch runtime execution records."
        ),
    )
    parser.add_argument("--report-json", required=True, help="exported comparison report JSON path")
    parser.add_argument(
        "--allow-absolute-paths",
        action="store_true",
        help="allow absolute run_path values instead of requiring portfolio-safe relative paths",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
