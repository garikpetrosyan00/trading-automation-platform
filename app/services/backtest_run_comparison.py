import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class BacktestRunComparisonError(ValueError):
    pass


METRICS = (
    "final_equity",
    "final_balance",
    "total_return_pct",
    "trades_count",
    "win_rate_pct",
    "max_drawdown_pct",
    "fees_paid",
)


def compare_backtest_run_dirs(base_run_dir: str | Path, candidate_run_dir: str | Path) -> dict[str, Any]:
    base_dir = Path(base_run_dir)
    candidate_dir = Path(candidate_run_dir)
    base_summary = _load_summary(base_dir)
    candidate_summary = _load_summary(candidate_dir)

    return {
        "result": "PASS",
        "base_run_dir": str(base_dir),
        "candidate_run_dir": str(candidate_dir),
        "metrics": {
            metric: _compare_metric(base_summary, candidate_summary, metric)
            for metric in METRICS
        },
        "artifacts": {
            "base": _artifact_summary(base_dir),
            "candidate": _artifact_summary(candidate_dir),
        },
    }


def compare_backtest_summaries(
    *,
    base_summary_path: str | Path,
    candidate_summary_path: str | Path,
) -> dict[str, Any]:
    base_path = Path(base_summary_path)
    candidate_path = Path(candidate_summary_path)
    base_summary = _load_summary_file(base_path, label="base summary")
    candidate_summary = _load_summary_file(candidate_path, label="candidate summary")

    return {
        "result": "PASS",
        "base_summary_path": str(base_path),
        "candidate_summary_path": str(candidate_path),
        "metrics": {
            metric: _compare_metric(base_summary, candidate_summary, metric)
            for metric in METRICS
        },
    }


def compact_backtest_comparison_report(report: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "result": report["result"],
        "deltas": {
            metric: details["delta"] if details["available"] else None
            for metric, details in report["metrics"].items()
        },
        "unavailable_metrics": [
            metric
            for metric, details in report["metrics"].items()
            if not details["available"]
        ],
    }
    for key in ("base_run_dir", "candidate_run_dir", "base_summary_path", "candidate_summary_path"):
        if key in report:
            compact[key] = report[key]
    return compact


def _load_summary(run_dir: Path) -> dict[str, Any]:
    if not run_dir.exists():
        raise BacktestRunComparisonError(f"run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise BacktestRunComparisonError(f"run path is not a directory: {run_dir}")

    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise BacktestRunComparisonError(f"summary.json does not exist: {summary_path}")
    if not summary_path.is_file():
        raise BacktestRunComparisonError(f"summary.json path is not a file: {summary_path}")
    return _load_summary_file(summary_path, label="summary.json")


def _load_summary_file(path: Path, *, label: str) -> dict[str, Any]:
    if not path.exists():
        raise BacktestRunComparisonError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise BacktestRunComparisonError(f"{label} path is not a file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BacktestRunComparisonError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise BacktestRunComparisonError(f"{label} must contain a JSON object: {path}")
    return payload


def _compare_metric(base: dict[str, Any], candidate: dict[str, Any], metric: str) -> dict[str, Any]:
    base_value = base.get(metric)
    candidate_value = candidate.get(metric)
    if base_value in (None, "") or candidate_value in (None, ""):
        return {
            "available": False,
            "base": _json_value(base_value),
            "candidate": _json_value(candidate_value),
            "delta": None,
            "reason": "metric missing or null",
        }
    try:
        base_decimal = Decimal(str(base_value))
        candidate_decimal = Decimal(str(candidate_value))
    except (InvalidOperation, ValueError) as exc:
        return {
            "available": False,
            "base": _json_value(base_value),
            "candidate": _json_value(candidate_value),
            "delta": None,
            "reason": f"metric is not numeric: {exc}",
        }
    if not base_decimal.is_finite() or not candidate_decimal.is_finite():
        return {
            "available": False,
            "base": _json_value(base_value),
            "candidate": _json_value(candidate_value),
            "delta": None,
            "reason": "metric is not finite",
        }
    return {
        "available": True,
        "base": _decimal_to_string(base_decimal),
        "candidate": _decimal_to_string(candidate_decimal),
        "delta": _decimal_to_string(candidate_decimal - base_decimal),
    }


def _artifact_summary(run_dir: Path) -> dict[str, Any]:
    return {
        "summary_json": (run_dir / "summary.json").is_file(),
        "trades_csv": (run_dir / "trades.csv").is_file(),
        "trades_count": _count_csv_rows(run_dir / "trades.csv"),
        "equity_curve_csv": (run_dir / "equity_curve.csv").is_file(),
        "equity_points_count": _count_csv_rows(run_dir / "equity_curve.csv"),
    }


def _count_csv_rows(path: Path) -> int | None:
    if not path.is_file():
        return None
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _row in csv.DictReader(handle))


def _decimal_to_string(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal_to_string(value)
    return value
