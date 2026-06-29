import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from app.services.backtest_dataset import (
    DatasetPreparationError,
    parse_date_boundary,
    prepare_backtest_dataset,
    summary_to_jsonable,
)


class CliArgumentError(Exception):
    pass


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(message)


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        summary = prepare_backtest_dataset(
            input_paths=args.input,
            output_path=args.output,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start=parse_date_boundary(args.start) if args.start is not None else None,
            end=parse_date_boundary(args.end) if args.end is not None else None,
            dedupe=args.dedupe,
            overwrite=args.overwrite,
        )
        payload = summary_to_jsonable(summary)
        if args.summary_json is not None:
            summary_path = Path(args.summary_json)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, sort_keys=True), file=stdout)
        return 0
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except DatasetPreparationError as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="prepare-backtest-dataset",
        description="Prepare local OHLCV CSV files for the CSV backtest runner. No network or runtime execution.",
    )
    parser.add_argument("--symbol", required=True, help="trading symbol, for example BTCUSDT")
    parser.add_argument("--timeframe", required=True, help="timeframe label, for example 1h")
    parser.add_argument("--input", action="append", required=True, help="raw candle CSV input path; repeatable")
    parser.add_argument("--output", required=True, help="canonical CSV output path")
    parser.add_argument("--start", help="inclusive UTC start timestamp/date, for example 2025-01-01")
    parser.add_argument("--end", help="exclusive UTC end timestamp/date, for example 2026-01-01")
    parser.add_argument("--dedupe", choices=["keep-first", "keep-last"], help="handle duplicate timestamps")
    parser.add_argument("--summary-json", help="optional path to write summary JSON")
    parser.add_argument("--overwrite", action="store_true", help="allow replacing the output CSV")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
