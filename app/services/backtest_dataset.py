from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ZERO = Decimal("0")
CANONICAL_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
TIMESTAMP_ALIASES = ("timestamp", "open_time", "time", "date")
TIMEFRAME_DELTAS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


class DatasetPreparationError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedCandle:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class DatasetSummary:
    symbol: str
    timeframe: str
    rows_in: int
    rows_out: int
    first_timestamp: datetime | None
    last_timestamp: datetime | None
    duplicate_timestamps_count: int
    missing_intervals_count: int
    largest_gap: str | None
    output_path: str


def prepare_backtest_dataset(
    *,
    input_paths: list[str | Path],
    output_path: str | Path,
    symbol: str,
    timeframe: str,
    start: datetime | None = None,
    end: datetime | None = None,
    dedupe: str | None = None,
    overwrite: bool = False,
) -> DatasetSummary:
    if not input_paths:
        raise DatasetPreparationError("at least one --input file is required")
    if dedupe not in {None, "keep-first", "keep-last"}:
        raise DatasetPreparationError("dedupe must be one of: keep-first, keep-last")
    if start is not None and end is not None and start >= end:
        raise DatasetPreparationError("start must be before end")

    output = Path(output_path)
    if output.exists() and output.is_dir():
        raise DatasetPreparationError(f"output path points to a directory: {output}")
    if output.exists() and not overwrite:
        raise DatasetPreparationError(f"output file already exists; pass --overwrite to replace: {output}")

    candles: list[PreparedCandle] = []
    rows_in = 0
    for path in input_paths:
        loaded, count = _load_input_file(Path(path))
        candles.extend(loaded)
        rows_in += count

    if start is not None:
        candles = [candle for candle in candles if candle.timestamp >= start]
    if end is not None:
        candles = [candle for candle in candles if candle.timestamp < end]

    duplicate_count = _duplicate_count(candles)
    candles = _dedupe_or_reject(candles, dedupe=dedupe)
    candles = sorted(candles, key=lambda candle: candle.timestamp)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        for candle in candles:
            writer.writerow(_candle_row(candle))

    gap_summary = _gap_summary(candles, timeframe)
    return DatasetSummary(
        symbol=symbol.strip().upper(),
        timeframe=timeframe.strip(),
        rows_in=rows_in,
        rows_out=len(candles),
        first_timestamp=candles[0].timestamp if candles else None,
        last_timestamp=candles[-1].timestamp if candles else None,
        duplicate_timestamps_count=duplicate_count,
        missing_intervals_count=gap_summary["missing_intervals_count"],
        largest_gap=gap_summary["largest_gap"],
        output_path=str(output),
    )


def parse_date_boundary(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DatasetPreparationError(f"date boundary is not parseable: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def summary_to_jsonable(summary: DatasetSummary) -> dict[str, object]:
    return {
        "symbol": summary.symbol,
        "timeframe": summary.timeframe,
        "rows_in": summary.rows_in,
        "rows_out": summary.rows_out,
        "first_timestamp": _iso_z(summary.first_timestamp) if summary.first_timestamp is not None else None,
        "last_timestamp": _iso_z(summary.last_timestamp) if summary.last_timestamp is not None else None,
        "duplicate_timestamps_count": summary.duplicate_timestamps_count,
        "missing_intervals_count": summary.missing_intervals_count,
        "largest_gap": summary.largest_gap,
        "output_path": summary.output_path,
    }


def _load_input_file(path: Path) -> tuple[list[PreparedCandle], int]:
    if not path.exists():
        raise DatasetPreparationError(f"input file does not exist: {path}")
    if not path.is_file():
        raise DatasetPreparationError(f"input path is not a file: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DatasetPreparationError(f"input CSV is empty: {path}")
        column_map = _column_map(reader.fieldnames, path)
        candles: list[PreparedCandle] = []
        rows_in = 0
        for row_number, row in enumerate(reader, start=2):
            rows_in += 1
            candles.append(_parse_row(row, column_map=column_map, path=path, row_number=row_number))
    if rows_in == 0:
        raise DatasetPreparationError(f"input CSV contains no rows: {path}")
    return candles, rows_in


def _column_map(fieldnames: list[str], path: Path) -> dict[str, str]:
    normalized = {field.strip().lower(): field for field in fieldnames}
    mapped: dict[str, str] = {}
    timestamp_column = next((normalized[alias] for alias in TIMESTAMP_ALIASES if alias in normalized), None)
    if timestamp_column is None:
        raise DatasetPreparationError(f"{path}: missing required timestamp column")
    mapped["timestamp"] = timestamp_column
    for column in ("open", "high", "low", "close", "volume"):
        if column not in normalized:
            raise DatasetPreparationError(f"{path}: missing required column: {column}")
        mapped[column] = normalized[column]
    return mapped


def _parse_row(row: dict[str, str], *, column_map: dict[str, str], path: Path, row_number: int) -> PreparedCandle:
    timestamp = _parse_timestamp(row[column_map["timestamp"]], path=path, row_number=row_number)
    open_price = _parse_decimal(row[column_map["open"]], "open", path=path, row_number=row_number, positive=True)
    high_price = _parse_decimal(row[column_map["high"]], "high", path=path, row_number=row_number, positive=True)
    low_price = _parse_decimal(row[column_map["low"]], "low", path=path, row_number=row_number, positive=True)
    close_price = _parse_decimal(row[column_map["close"]], "close", path=path, row_number=row_number, positive=True)
    volume = _parse_decimal(row[column_map["volume"]], "volume", path=path, row_number=row_number, positive=False)
    if volume < ZERO:
        raise DatasetPreparationError(f"{path}: row {row_number}: volume must not be negative")
    if high_price < low_price:
        raise DatasetPreparationError(f"{path}: row {row_number}: high must be greater than or equal to low")
    if high_price < open_price or high_price < close_price:
        raise DatasetPreparationError(f"{path}: row {row_number}: high must be greater than or equal to open and close")
    if low_price > open_price or low_price > close_price:
        raise DatasetPreparationError(f"{path}: row {row_number}: low must be less than or equal to open and close")
    return PreparedCandle(
        timestamp=timestamp,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=volume,
    )


def _parse_timestamp(value: str, *, path: Path, row_number: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DatasetPreparationError(f"{path}: row {row_number}: timestamp is not parseable") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_decimal(value: str, name: str, *, path: Path, row_number: int, positive: bool) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DatasetPreparationError(f"{path}: row {row_number}: {name} must be a decimal") from exc
    if not parsed.is_finite():
        raise DatasetPreparationError(f"{path}: row {row_number}: {name} must be finite")
    if positive and parsed <= ZERO:
        raise DatasetPreparationError(f"{path}: row {row_number}: {name} must be positive")
    return parsed


def _duplicate_count(candles: list[PreparedCandle]) -> int:
    seen: set[datetime] = set()
    duplicates = 0
    for candle in candles:
        if candle.timestamp in seen:
            duplicates += 1
        seen.add(candle.timestamp)
    return duplicates


def _dedupe_or_reject(candles: list[PreparedCandle], *, dedupe: str | None) -> list[PreparedCandle]:
    by_timestamp: dict[datetime, PreparedCandle] = {}
    duplicates: set[datetime] = set()
    for candle in candles:
        if candle.timestamp in by_timestamp:
            duplicates.add(candle.timestamp)
            if dedupe == "keep-last":
                by_timestamp[candle.timestamp] = candle
        else:
            by_timestamp[candle.timestamp] = candle
    if duplicates and dedupe is None:
        first = sorted(duplicates)[0]
        raise DatasetPreparationError(f"duplicate timestamp found: {_iso_z(first)}")
    return list(by_timestamp.values())


def _gap_summary(candles: list[PreparedCandle], timeframe: str) -> dict[str, int | str | None]:
    expected_delta = TIMEFRAME_DELTAS.get(timeframe)
    if expected_delta is None or len(candles) < 2:
        return {"missing_intervals_count": 0, "largest_gap": None}
    missing = 0
    largest_gap: timedelta | None = None
    for previous, current in zip(candles, candles[1:]):
        gap = current.timestamp - previous.timestamp
        if gap > expected_delta:
            missing += int(gap / expected_delta) - 1
            if largest_gap is None or gap > largest_gap:
                largest_gap = gap
    return {
        "missing_intervals_count": missing,
        "largest_gap": _timedelta_label(largest_gap) if largest_gap is not None else None,
    }


def _candle_row(candle: PreparedCandle) -> dict[str, str]:
    return {
        "timestamp": _iso_z(candle.timestamp),
        "open": _decimal_string(candle.open),
        "high": _decimal_string(candle.high),
        "low": _decimal_string(candle.low),
        "close": _decimal_string(candle.close),
        "volume": _decimal_string(candle.volume),
    }


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _decimal_string(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _timedelta_label(value: timedelta) -> str:
    total_seconds = int(value.total_seconds())
    if total_seconds % 86400 == 0:
        return f"{total_seconds // 86400}d"
    if total_seconds % 3600 == 0:
        return f"{total_seconds // 3600}h"
    if total_seconds % 60 == 0:
        return f"{total_seconds // 60}m"
    return f"{total_seconds}s"
