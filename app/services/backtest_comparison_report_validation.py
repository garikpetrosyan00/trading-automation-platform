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
    "breakeven_count",
    "win_rate_pct",
    "average_winning_trade_pnl",
    "average_losing_trade_pnl",
    "average_trade_pnl",
    "best_trade_pnl",
    "worst_trade_pnl",
    "profit_factor",
    "max_drawdown_amount",
    "max_drawdown_pct",
    "exposure_pct",
    "overall_score",
)
NUMERIC_SCORE_COMPONENT_FIELDS = (
    "return_score",
    "drawdown_score",
    "profit_factor_score",
    "win_rate_score",
    "trade_count_score",
    "exposure_score",
    "final_normalized_score",
)
NUMERIC_RECOMMENDATION_RUN_FIELDS = (
    "overall_score",
    "total_return_pct",
    "max_drawdown_pct",
    "max_drawdown_amount",
    "profit_factor",
    "win_rate",
    "trade_count",
    "exposure_pct",
)
RECOMMENDATION_STATUSES = {"recommended", "weak_recommendation", "not_recommended", "no_valid_runs"}
ACCEPTANCE_STATUSES = {"accepted", "accepted_with_warnings", "rejected", "not_evaluated"}
ACCEPTANCE_GATE_SEVERITIES = {"failure", "warning"}
EXECUTIVE_DECISIONS = {"accept_candidate", "accept_with_warnings", "reject_candidate", "no_decision"}
EXECUTIVE_NEXT_ACTIONS = {
    "promote_to_further_local_testing",
    "review_with_caution",
    "reject_or_adjust_strategy",
    "add_more_data_and_rerun",
    "no_action_available",
}


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
    _check_recommendation(
        report.get("recommendation"),
        run_names=run_names,
        errors=errors,
        checked_fields=checked_fields,
        allow_absolute_paths=allow_absolute_paths,
    )
    _check_executive_summary(report.get("executive_summary"), errors=errors, checked_fields=checked_fields)
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
            if field in summary and summary.get(field) not in (None, "") and not _is_numeric(summary.get(field)):
                errors.append(f"runs[{index}].summary.{field} must be numeric")
        if item.get("overall_score") not in (None, "") and not _is_numeric(item.get("overall_score")):
            errors.append(f"runs[{index}].overall_score must be numeric")
        score_components = item.get("score_components")
        if score_components is not None:
            if not isinstance(score_components, dict):
                errors.append(f"runs[{index}].score_components must be an object")
            else:
                for field in NUMERIC_SCORE_COMPONENT_FIELDS:
                    if field in score_components and score_components.get(field) not in (None, "") and not _is_numeric(score_components.get(field)):
                        errors.append(f"runs[{index}].score_components.{field} must be numeric")
        score_warnings = item.get("score_warnings")
        if score_warnings is not None and (
            not isinstance(score_warnings, list) or any(not isinstance(warning, str) for warning in score_warnings)
        ):
            errors.append(f"runs[{index}].score_warnings must be a list of strings")
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


def _check_recommendation(
    recommendation: Any,
    *,
    run_names: set[str],
    errors: list[str],
    checked_fields: list[str],
    allow_absolute_paths: bool,
) -> None:
    checked_fields.append("recommendation")
    if recommendation is None:
        return
    if not isinstance(recommendation, dict):
        errors.append("recommendation must be an object when present")
        return
    status = recommendation.get("recommendation_status")
    if status not in RECOMMENDATION_STATUSES:
        errors.append("recommendation.recommendation_status is invalid")
    recommended_run = recommendation.get("recommended_run")
    if status == "no_valid_runs":
        if recommended_run is not None:
            errors.append("recommendation.recommended_run must be null when status is no_valid_runs")
    elif not isinstance(recommended_run, dict):
        errors.append("recommendation.recommended_run must be an object")
    else:
        _check_recommendation_run(
            recommended_run,
            label="recommendation.recommended_run",
            run_names=run_names,
            errors=errors,
            allow_absolute_paths=allow_absolute_paths,
        )
    reason = recommendation.get("recommendation_reason")
    if not isinstance(reason, dict):
        errors.append("recommendation.recommendation_reason must be an object")
    else:
        for field in ("highest_overall_score", "positive_return", "acceptable_drawdown", "sufficient_trades", "better_risk_adjusted_profile"):
            if field in reason and not isinstance(reason.get(field), bool):
                errors.append(f"recommendation.recommendation_reason.{field} must be boolean")
        if reason.get("score_gap_to_runner_up") not in (None, "") and not _is_numeric(reason.get("score_gap_to_runner_up")):
            errors.append("recommendation.recommendation_reason.score_gap_to_runner_up must be numeric")
    _check_string_list(
        recommendation.get("recommendation_warnings"),
        label="recommendation.recommendation_warnings",
        errors=errors,
    )
    _check_acceptance(recommendation, errors=errors)
    runner_up_runs = recommendation.get("runner_up_runs")
    if runner_up_runs is not None:
        if not isinstance(runner_up_runs, list):
            errors.append("recommendation.runner_up_runs must be a list")
        else:
            for index, item in enumerate(runner_up_runs):
                if not isinstance(item, dict):
                    errors.append(f"recommendation.runner_up_runs[{index}] must be an object")
                    continue
                _check_recommendation_run(
                    item,
                    label=f"recommendation.runner_up_runs[{index}]",
                    run_names=run_names,
                    errors=errors,
                    allow_absolute_paths=allow_absolute_paths,
                )


def _check_recommendation_run(
    item: dict[str, Any],
    *,
    label: str,
    run_names: set[str],
    errors: list[str],
    allow_absolute_paths: bool,
) -> None:
    run_name = item.get("run_name")
    if run_name is not None and run_name not in run_names:
        errors.append(f"{label}.run_name references unknown run: {run_name}")
    _check_safe_path(
        item.get("run_path"),
        label=f"{label}.run_path",
        errors=errors,
        allow_absolute_paths=allow_absolute_paths,
    )
    for field in NUMERIC_RECOMMENDATION_RUN_FIELDS:
        if field in item and item.get(field) not in (None, "") and not _is_numeric(item.get(field)):
            errors.append(f"{label}.{field} must be numeric")
    _check_string_list(item.get("score_warnings"), label=f"{label}.score_warnings", errors=errors)


def _check_acceptance(recommendation: dict[str, Any], *, errors: list[str]) -> None:
    if not any(field in recommendation for field in ("acceptance_status", "acceptance_gates", "acceptance_failures", "acceptance_warnings")):
        return
    if recommendation.get("acceptance_status") not in ACCEPTANCE_STATUSES:
        errors.append("recommendation.acceptance_status is invalid")
    gates = recommendation.get("acceptance_gates")
    if not isinstance(gates, list):
        errors.append("recommendation.acceptance_gates must be a list")
    else:
        for index, gate in enumerate(gates):
            if not isinstance(gate, dict):
                errors.append(f"recommendation.acceptance_gates[{index}] must be an object")
                continue
            if not isinstance(gate.get("name"), str) or not gate.get("name"):
                errors.append(f"recommendation.acceptance_gates[{index}].name must be a non-empty string")
            if not isinstance(gate.get("passed"), bool):
                errors.append(f"recommendation.acceptance_gates[{index}].passed must be boolean")
            if gate.get("severity") not in ACCEPTANCE_GATE_SEVERITIES:
                errors.append(f"recommendation.acceptance_gates[{index}].severity is invalid")
            if not isinstance(gate.get("reason"), str) or not gate.get("reason"):
                errors.append(f"recommendation.acceptance_gates[{index}].reason must be a non-empty string")
            if _contains_non_finite_number(gate.get("actual")):
                errors.append(f"recommendation.acceptance_gates[{index}].actual must be finite")
            if _contains_non_finite_number(gate.get("threshold")):
                errors.append(f"recommendation.acceptance_gates[{index}].threshold must be finite")
    _check_string_list(
        recommendation.get("acceptance_failures"),
        label="recommendation.acceptance_failures",
        errors=errors,
    )
    _check_string_list(
        recommendation.get("acceptance_warnings"),
        label="recommendation.acceptance_warnings",
        errors=errors,
    )


def _check_executive_summary(executive_summary: Any, *, errors: list[str], checked_fields: list[str]) -> None:
    checked_fields.append("executive_summary")
    if executive_summary is None:
        return
    if not isinstance(executive_summary, dict):
        errors.append("executive_summary must be an object when present")
        return
    for field in ("title", "decision", "acceptance_status", "recommendation_status", "next_action", "summary_text"):
        if not isinstance(executive_summary.get(field), str) or not executive_summary.get(field):
            errors.append(f"executive_summary.{field} must be a non-empty string")
    if executive_summary.get("decision") not in EXECUTIVE_DECISIONS:
        errors.append("executive_summary.decision is invalid")
    if executive_summary.get("acceptance_status") not in ACCEPTANCE_STATUSES:
        errors.append("executive_summary.acceptance_status is invalid")
    if executive_summary.get("recommendation_status") not in RECOMMENDATION_STATUSES:
        errors.append("executive_summary.recommendation_status is invalid")
    if executive_summary.get("next_action") not in EXECUTIVE_NEXT_ACTIONS:
        errors.append("executive_summary.next_action is invalid")
    for field in ("best_strategy", "best_run_label"):
        if executive_summary.get(field) is not None and not isinstance(executive_summary.get(field), str):
            errors.append(f"executive_summary.{field} must be a string")
    if executive_summary.get("overall_score") not in (None, "") and not _is_numeric(executive_summary.get("overall_score")):
        errors.append("executive_summary.overall_score must be numeric")
    _check_string_list(executive_summary.get("key_strengths"), label="executive_summary.key_strengths", errors=errors)
    _check_string_list(executive_summary.get("key_risks"), label="executive_summary.key_risks", errors=errors)
    if _contains_non_finite_number(executive_summary):
        errors.append("executive_summary values must be finite")


def _check_string_list(value: Any, *, label: str, errors: list[str]) -> None:
    if value is not None and (not isinstance(value, list) or any(not isinstance(item, str) for item in value)):
        errors.append(f"{label} must be a list of strings")


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


def _contains_non_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return True
        return not parsed.is_finite()
    if isinstance(value, list):
        return any(_contains_non_finite_number(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_non_finite_number(item) for item in value.values())
    return False
