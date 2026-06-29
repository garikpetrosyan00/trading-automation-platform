import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from app.cli.run_backtest import CliArgumentError, SafeArgumentParser
from app.services.backtest_run_comparison import (
    BacktestRunComparisonError,
    compact_backtest_comparison_report,
    compare_backtest_run_dirs,
)


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        report = compare_backtest_run_dirs(args.base_run_dir, args.candidate_run_dir)
        output_payload = compact_backtest_comparison_report(report) if args.compact else report
        output = json.dumps(output_payload, sort_keys=True)
        if args.output_json is not None:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output + "\n", encoding="utf-8")
        print(output, file=stdout)
        return 0
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (BacktestRunComparisonError, OSError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="compare-backtest-runs",
        description=(
            "Compare two saved local CSV backtest run directories. File-based only; "
            "does not contact exchanges or touch runtime execution records."
        ),
    )
    parser.add_argument("--base-run-dir", required=True, help="baseline run directory containing summary.json")
    parser.add_argument("--candidate-run-dir", required=True, help="candidate run directory containing summary.json")
    parser.add_argument("--output-json", help="optional path to write the JSON comparison report")
    parser.add_argument("--compact", action="store_true", help="print compact metric deltas instead of full details")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
