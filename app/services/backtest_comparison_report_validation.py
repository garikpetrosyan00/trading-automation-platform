import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ("generated_at", "run_count", "runs", "rankings", "safety_note")
NUMERIC_SUMMARY_FIELDS = (
    "starting_balance",
    "ending_balance",
    "final_balance",
    "final_equity",
    "total_return",
    "total_return_pct",
    "realized_pnl",
    "trades_count",
    "completed_round_trips",
    "win_count",
    "loss_count",
    "win_rate_pct",
    "max_drawdown_pct",
)


class BacktestComparisonReportValidationError(ValueError):
    pass


def load_report_json(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)
    if not report_path.exists():
        raise BacktestComparisonReportValidationError(f"report JSON does not exist: {report_path}")
    if not report_path.is_file():
        raise BacktestComparisonReportValidationError(f"report JSON path is not a file: {report_path}")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BacktestComparisonReportValidationError(f"report JSON is not valid JSON: {report_path}") from exc
    if not isinstance(payload, dict):
        raise BacktestComparisonReportValidationError(f"report JSON must contain a JSON object: {report_path}")
    return payload


def validate_backtest_comparison_report(
    report: dict[str, Any],
    *,
    allow_absolute_paths: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked_fields: list[str] = []

    _check_required_fields(report, errors=errors, checked_fields=checked_fields)
    runs = report.get("runs")
    rankings = report.get("rankings")

    if isinstance(runs, list):
        checked_fields.append("run_count_matches_runs")
        if report.get("run_count") != len(runs):
            errors.append("run_count does not match runs length")
    else:
        errors.append("runs must be a list of run summaries")
        runs = []

    run_names = _check_runs(
        runs,
        errors=errors,
        warnings=warnings,
        checked_fields=checked_fields,
        allow_absolute_paths=allow_absolute_paths,
    )
    _check_rankings(
        rankings,
        run_names=run_names,
        errors=errors,
        checked_fields=checked_fields,
        allow_absolute_paths=allow_absolute_paths,
    )
    _check_safety_note(report.get("safety_note"), errors=errors, checked_fields=checked_fields)

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_fields": checked_fields,
    }


def _check_required_fields(report: dict[str, Any], *, errors: list[str], checked_fields: list[str]) -> None:
    for field in REQUIRED_FIELDS:
        checked_fields.append(field)
        if field not in report:
            errors.append(f"missing required field: {field}")


def _check_runs(
    runs: list[Any],
    *,
    errors: list[str],
    warnings: list[str],
    checked_fields: list[str],
    allow_absolute_paths: bool,
) -> set[str]:
    checked_fields.append("run_summaries")
    run_names: set[str] = set()
    for index, item in enumerate(runs):
        if not isinstance(item, dict):
            errors.append(f"runs[{index}] must be an object")
            continue
        run_name = item.get("run_name")
        if not isinstance(run_name, str) or not run_name:
            errors.append(f"runs[{index}].run_name must be a non-empty string")
        else:
            if run_name in run_names:
                warnings.append(f"duplicate run_name: {run_name}")
            run_names.add(run_name)

        _check_safe_path(
            item.get("run_path"),
            label=f"runs[{index}].run_path",
            errors=errors,
            allow_absolute_paths=allow_absolute_paths,
        )
        summary = item.get("summary")
        if not isinstance(summary, dict):
            errors.append(f"runs[{index}].summary must be an object")
            continue
        for field in NUMERIC_SUMMARY_FIELDS:
            if field in summary and not _is_numeric(summary.get(field)):
                errors.append(f"runs[{index}].summary.{field} must be numeric")
    return run_names


def _check_rankings(
    rankings: Any,
    *,
    run_names: set[str],
    errors: list[str],
    checked_fields: list[str],
    allow_absolute_paths: bool,
) -> None:
    checked_fields.append("ranking_references")
    if not isinstance(rankings, dict):
        errors.append("rankings must be an object")
        return
    for metric, items in rankings.items():
        if not isinstance(items, list):
            errors.append(f"rankings.{metric} must be a list")
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"rankings.{metric}[{index}] must be an object")
                continue
            run_name = item.get("run_name")
            if run_name not in run_names:
                errors.append(f"rankings.{metric}[{index}] references unknown run: {run_name}")
            _check_safe_path(
                item.get("run_path"),
                label=f"rankings.{metric}[{index}].run_path",
                errors=errors,
                allow_absolute_paths=allow_absolute_paths,
            )
            if item.get("available") is True and not _is_numeric(item.get("value")):
                errors.append(f"rankings.{metric}[{index}].value must be numeric when available")


def _check_safety_note(value: Any, *, errors: list[str], checked_fields: list[str]) -> None:
    checked_fields.append("safety_note_content")
    if not isinstance(value, str) or not value.strip():
        errors.append("safety_note must be a non-empty string")
        return
    lowered = value.lower()
    for phrase in ("local", "no live", "db writes", "orders", "execution attempts", "reconciliation"):
        if phrase not in lowered:
            errors.append(f"safety_note missing required safety phrase: {phrase}")


def _check_safe_path(value: Any, *, label: str, errors: list[str], allow_absolute_paths: bool) -> None:
    if value in (None, ""):
        return
    if not isinstance(value, str):
        errors.append(f"{label} must be a string")
        return
    path = Path(value)
    if path.is_absolute() and not allow_absolute_paths:
        errors.append(f"{label} must not expose an absolute path")
    if ".." in path.parts:
        errors.append(f"{label} must not contain path traversal")


def _is_numeric(value: Any) -> bool:
    if isinstance(value, bool) or value in (None, ""):
        return False
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    return parsed.is_finite()
