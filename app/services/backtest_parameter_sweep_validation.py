import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


VALIDATION_STATUSES = {"passed", "passed_with_warnings", "failed"}
RECOMMENDATION_STATUSES = {"recommended", "weak_recommendation", "not_recommended", "no_valid_runs"}
ACCEPTANCE_STATUSES = {"accepted", "accepted_with_warnings", "rejected", "not_evaluated"}
EXECUTIVE_DECISIONS = {"accept_candidate", "accept_with_warnings", "reject_candidate", "no_decision"}
NUMERIC_PARAMETER_SET_FIELDS = (
    "overall_score",
    "total_return_pct",
    "max_drawdown_pct",
    "max_drawdown_amount",
    "profit_factor",
    "win_rate",
    "trade_count",
)


class BacktestParameterSweepValidationError(ValueError):
    pass


def validate_backtest_parameter_sweep_output(sweep_dir: str | Path) -> dict[str, Any]:
    root = Path(sweep_dir)
    errors: list[str] = []
    warnings: list[str] = []
    checked_artifacts: list[str] = []

    summary_path = root / "sweep_summary.json"
    report_path = root / "sweep_report.md"
    results_path = root / "sweep_results.csv"

    summary = _load_summary(summary_path, errors=errors, checked_artifacts=checked_artifacts)
    csv_rows = _load_results_csv(results_path, errors=errors, warnings=warnings, checked_artifacts=checked_artifacts)
    _check_markdown_report(report_path, warnings=warnings, checked_artifacts=checked_artifacts)

    checked_row_count = len(csv_rows) if csv_rows is not None else _summary_results_count(summary)
    if summary is not None:
        _check_summary(
            summary,
            csv_row_count=len(csv_rows) if csv_rows is not None else None,
            errors=errors,
            warnings=warnings,
        )

    status = _validation_status(errors, warnings)
    return {
        "schema_version": "1",
        "validation_status": status,
        "validation_errors": errors,
        "validation_warnings": warnings,
        "checked_artifacts": checked_artifacts,
        "checked_row_count": checked_row_count,
    }


def _load_summary(path: Path, *, errors: list[str], checked_artifacts: list[str]) -> dict[str, Any] | None:
    checked_artifacts.append("sweep_summary.json")
    if not path.exists():
        errors.append("sweep_summary.json is missing")
        return None
    if not path.is_file():
        errors.append("sweep_summary.json path is not a file")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append("sweep_summary.json is not valid JSON")
        return None
    if not isinstance(payload, dict):
        errors.append("sweep_summary.json must contain a JSON object")
        return None
    return payload


def _load_results_csv(
    path: Path,
    *,
    errors: list[str],
    warnings: list[str],
    checked_artifacts: list[str],
) -> list[dict[str, Any]] | None:
    checked_artifacts.append("sweep_results.csv")
    if not path.exists():
        warnings.append("sweep_results_csv_missing")
        return None
    if not path.is_file():
        errors.append("sweep_results.csv path is not a file")
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except csv.Error:
        errors.append("sweep_results.csv is not readable CSV")
        return None


def _check_markdown_report(path: Path, *, warnings: list[str], checked_artifacts: list[str]) -> None:
    checked_artifacts.append("sweep_report.md")
    if not path.exists():
        warnings.append("sweep_report_md_missing")
        return
    if not path.is_file():
        warnings.append("sweep_report_md_not_file")
        return
    content = path.read_text(encoding="utf-8")
    if "Backtest Parameter Sweep" not in content:
        warnings.append("sweep_report_md_missing_title")
    if "Sweep Summary" not in content:
        warnings.append("sweep_report_md_missing_sweep_summary")


def _check_summary(
    summary: dict[str, Any],
    *,
    csv_row_count: int | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    if _contains_non_finite_number(summary):
        errors.append("sweep_summary.json contains NaN or Infinity")
    if summary.get("result") != "PASS":
        errors.append("sweep_summary.result must be PASS")
    results = summary.get("results")
    if results is not None and not isinstance(results, list):
        errors.append("sweep_summary.results must be a list")
        results = []
    result_count = len(results) if isinstance(results, list) else 0
    if csv_row_count is not None and csv_row_count != result_count:
        errors.append("sweep_results.csv row count does not match sweep_summary.results length")
    combinations_count = summary.get("combinations_count")
    if combinations_count != result_count:
        errors.append("sweep_summary.combinations_count must match results length")

    nested = summary.get("sweep_summary")
    if nested is None:
        warnings.append("sweep_summary_missing_compatibility_mode")
        return
    if not isinstance(nested, dict):
        errors.append("sweep_summary.sweep_summary must be an object")
        return
    _check_sweep_summary(nested, result_count=result_count, csv_row_count=csv_row_count, errors=errors)


def _check_sweep_summary(
    payload: dict[str, Any],
    *,
    result_count: int,
    csv_row_count: int | None,
    errors: list[str],
) -> None:
    required_fields = (
        "best_parameter_set",
        "best_overall_score",
        "recommendation_status",
        "acceptance_status",
        "executive_decision",
        "tested_parameter_count",
        "accepted_count",
        "rejected_count",
        "warning_count",
        "top_parameter_sets",
        "warnings",
    )
    for field in required_fields:
        if field not in payload:
            errors.append(f"sweep_summary.{field} is missing")

    if payload.get("recommendation_status") not in RECOMMENDATION_STATUSES:
        errors.append("sweep_summary.recommendation_status is invalid")
    if payload.get("acceptance_status") not in ACCEPTANCE_STATUSES:
        errors.append("sweep_summary.acceptance_status is invalid")
    if payload.get("executive_decision") not in EXECUTIVE_DECISIONS:
        errors.append("sweep_summary.executive_decision is invalid")
    for field in ("tested_parameter_count", "accepted_count", "rejected_count", "warning_count"):
        if not isinstance(payload.get(field), int) or isinstance(payload.get(field), bool) or payload.get(field) < 0:
            errors.append(f"sweep_summary.{field} must be a non-negative integer")

    tested_count = payload.get("tested_parameter_count")
    if isinstance(tested_count, int):
        if tested_count != result_count:
            errors.append("sweep_summary.tested_parameter_count must match results length")
        if csv_row_count is not None and tested_count != csv_row_count:
            errors.append("sweep_summary.tested_parameter_count must match sweep_results.csv row count")
    accepted_count = payload.get("accepted_count")
    rejected_count = payload.get("rejected_count")
    if isinstance(tested_count, int) and isinstance(accepted_count, int) and isinstance(rejected_count, int):
        if accepted_count + rejected_count > tested_count:
            errors.append("sweep_summary accepted_count + rejected_count must not exceed tested_parameter_count")

    _check_string_list(payload.get("warnings"), "sweep_summary.warnings", errors=errors)
    if isinstance(payload.get("warning_count"), int) and isinstance(payload.get("warnings"), list):
        if payload["warning_count"] != len(payload["warnings"]):
            errors.append("sweep_summary.warning_count must match warnings length")
    if payload.get("best_overall_score") not in (None, "") and not _is_numeric(payload.get("best_overall_score")):
        errors.append("sweep_summary.best_overall_score must be finite numeric")

    best = payload.get("best_parameter_set")
    if best is not None:
        _check_parameter_set(best, label="sweep_summary.best_parameter_set", errors=errors)
    top_sets = payload.get("top_parameter_sets")
    if not isinstance(top_sets, list):
        errors.append("sweep_summary.top_parameter_sets must be a list")
    else:
        previous_key = None
        for index, item in enumerate(top_sets):
            if not isinstance(item, dict):
                errors.append(f"sweep_summary.top_parameter_sets[{index}] must be an object")
                continue
            _check_parameter_set(item, label=f"sweep_summary.top_parameter_sets[{index}]", errors=errors)
            key = _parameter_sort_key(item)
            if previous_key is not None and key < previous_key:
                errors.append("sweep_summary.top_parameter_sets must be sorted deterministically")
            previous_key = key


def _check_parameter_set(item: dict[str, Any], *, label: str, errors: list[str]) -> None:
    if not isinstance(item.get("strategy"), str) or not item.get("strategy"):
        errors.append(f"{label}.strategy must be a non-empty string")
    if not isinstance(item.get("parameters"), dict):
        errors.append(f"{label}.parameters must be an object")
    if item.get("acceptance_status") not in ACCEPTANCE_STATUSES:
        errors.append(f"{label}.acceptance_status is invalid")
    _check_string_list(item.get("score_warnings"), f"{label}.score_warnings", errors=errors)
    for field in NUMERIC_PARAMETER_SET_FIELDS:
        if field in item and item.get(field) not in (None, "") and not _is_numeric(item.get(field)):
            errors.append(f"{label}.{field} must be finite numeric")
    if _contains_non_finite_number(item):
        errors.append(f"{label} contains NaN or Infinity")


def _summary_results_count(summary: dict[str, Any] | None) -> int:
    if not isinstance(summary, dict):
        return 0
    results = summary.get("results")
    return len(results) if isinstance(results, list) else 0


def _validation_status(errors: list[str], warnings: list[str]) -> str:
    if errors:
        return "failed"
    if warnings:
        return "passed_with_warnings"
    return "passed"


def _check_string_list(value: Any, label: str, *, errors: list[str]) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"{label} must be a list of strings")


def _is_numeric(value: Any) -> bool:
    if isinstance(value, bool) or value in (None, ""):
        return False
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    return parsed.is_finite()


def _contains_non_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return True
        return not parsed.is_finite()
    if isinstance(value, str) and value in {"NaN", "Infinity", "-Infinity"}:
        return True
    if isinstance(value, list):
        return any(_contains_non_finite_number(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_non_finite_number(item) for item in value.values())
    return False


def _parameter_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    parameters = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
    return (
        -_decimal_sort_value(item.get("overall_score")),
        -_decimal_sort_value(item.get("total_return_pct")),
        _decimal_sort_value(item.get("max_drawdown_pct")),
        str(parameters.get("entry_below")),
        str(parameters.get("exit_above")),
        str(parameters.get("order_quantity")),
    )


def _decimal_sort_value(value: Any) -> Decimal:
    if value in (None, "", "Unavailable"):
        return Decimal("-999999999")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("-999999999")
    if not parsed.is_finite():
        return Decimal("-999999999")
    return parsed
