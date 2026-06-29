import json
import sys
from pathlib import Path
from typing import TextIO

from app.cli.run_backtest import CliArgumentError, SafeArgumentParser
from app.services.backtest_demo_bundle import BacktestDemoBundleError, export_backtest_demo_bundle


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        manifest = export_backtest_demo_bundle(
            run_dir=args.run_dir,
            comparison_json=args.comparison_json,
            report_md=args.report_md,
            output_dir=args.output_dir,
            title=args.title,
            overwrite=args.overwrite,
        )
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "output_dir": str(Path(args.output_dir)),
                    "files_count": len(manifest["files"]),
                    "comparison_included": manifest["comparison_included"],
                    "report_included": manifest["report_included"],
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
    except (BacktestDemoBundleError, OSError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        prog="export-backtest-demo-bundle",
        description=(
            "Package saved local CSV backtest artifacts into a clean demo folder. File-based only; "
            "does not contact exchanges or touch runtime execution records."
        ),
    )
    parser.add_argument("--run-dir", required=True, help="saved run directory containing summary.json")
    parser.add_argument("--comparison-json", help="optional comparison JSON to include as comparison.json")
    parser.add_argument("--report-md", help="optional Markdown report to include as report.md")
    parser.add_argument("--output-dir", required=True, help="demo bundle output directory")
    parser.add_argument("--title", help="optional bundle title")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing non-empty output directory")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
