import json
import sys
from typing import TextIO

from app.cli.run_backtest import CliArgumentError, SafeArgumentParser
from app.services.backtest_artifact_catalog import (
    BacktestArtifactCatalogError,
    build_backtest_artifact_catalog,
    compact_backtest_artifact_catalog,
)


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        catalog = build_backtest_artifact_catalog(args.artifact_root, artifact_type=args.artifact_type)
        payload = compact_backtest_artifact_catalog(catalog) if args.compact else catalog
        print(json.dumps(payload, sort_keys=True), file=stdout)
        return 0
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except (BacktestArtifactCatalogError, OSError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        prog="list-backtest-artifacts",
        description=(
            "List local CSV backtest artifacts under an artifact root. File-based only; "
            "does not contact exchanges or touch runtime execution records."
        ),
    )
    parser.add_argument("--artifact-root", required=True, help="local backtest artifact root, for example data/backtests/runs")
    parser.add_argument("--json", action="store_true", help="print JSON output")
    parser.add_argument("--compact", action="store_true", help="print compact JSON output")
    parser.add_argument("--artifact-type", choices=["run", "comparison_report", "sweep"], help="optional artifact type filter")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
