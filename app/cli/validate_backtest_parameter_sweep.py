import json
import sys
from typing import TextIO

from app.cli.run_backtest import CliArgumentError, SafeArgumentParser
from app.services.backtest_parameter_sweep_validation import (
    BacktestParameterSweepValidationError,
    validate_backtest_parameter_sweep_output,
)


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        result = validate_backtest_parameter_sweep_output(args.sweep_dir)
        print(json.dumps(result, sort_keys=True), file=stdout)
        return 0 if result["validation_status"] in {"passed", "passed_with_warnings"} else 1
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (BacktestParameterSweepValidationError, OSError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": "1",
                    "validation_status": "failed",
                    "validation_errors": [str(exc)],
                    "validation_warnings": [],
                    "checked_artifacts": [],
                    "checked_row_count": 0,
                },
                sort_keys=True,
            ),
            file=stdout,
        )
        return 1


def _build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        prog="validate-backtest-parameter-sweep",
        description=(
            "Validate local CSV backtest parameter sweep artifacts. File-based only; "
            "does not contact exchanges or touch runtime execution records."
        ),
    )
    parser.add_argument("--sweep-dir", required=True, help="directory containing sweep_summary.json")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
