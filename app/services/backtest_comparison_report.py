import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.backtest_run_comparison import build_backtest_executive_summary, build_backtest_recommendation_summary


SAFETY_NOTE = (
    "Local backtest artifact comparison report only; no live/testnet/Binance calls, "
    "DB writes, orders, fills, execution attempts, reconciliation jobs, or paper/live execution."
)

SUMMARY_FIELDS = (
    "run_name",
    "strategy_type",
    "entry_below",
    "exit_above",
    "fast_window",
    "slow_window",
    "order_quantity",
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


class BacktestComparisonReportError(ValueError):
    pass


def build_backtest_comparison_report(
    comparison: dict[str, Any],
    *,
    generated_at: str | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    if not isinstance(comparison, dict):
        raise BacktestComparisonReportError("comparison must be a JSON object")
    if comparison.get("result") != "PASS":
        raise BacktestComparisonReportError("comparison result must be PASS")
    runs = comparison.get("runs")
    rankings = comparison.get("rankings")
    if not isinstance(runs, list) or not isinstance(rankings, dict):
        raise BacktestComparisonReportError("comparison must include multi-run runs and rankings")

    root = Path(artifact_root).resolve() if artifact_root is not None else None
    report_runs = [_report_run(item, artifact_root=root) for item in runs]
    recommendation = comparison.get("recommendation")
    if not isinstance(recommendation, dict):
        recommendation = build_backtest_recommendation_summary(_runs_with_overall_scores_from_rankings(runs, rankings))
    executive_summary = comparison.get("executive_summary")
    if not isinstance(executive_summary, dict):
        executive_summary = build_backtest_executive_summary(recommendation)
    return {
        "result": "PASS",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_count": len(runs),
        "ranking_metrics": list(comparison.get("ranking_metrics", [])),
        "runs": report_runs,
        "rankings": _report_rankings(rankings, artifact_root=root),
        "recommendation": _report_recommendation(recommendation, artifact_root=root),
        "executive_summary": executive_summary,
        "safety_note": SAFETY_NOTE,
    }


def build_backtest_comparison_markdown_report(report: dict[str, Any], *, title: str = "Backtest Comparison Report") -> str:
    rows = [
        (
            run.get("run_name"),
            run.get("run_path"),
            run.get("summary", {}).get("strategy_type"),
            run.get("summary", {}).get("total_return"),
            run.get("summary", {}).get("ending_balance"),
            run.get("summary", {}).get("max_drawdown_pct"),
            run.get("overall_score") or run.get("summary", {}).get("overall_score"),
            ", ".join(run.get("score_warnings", [])) if isinstance(run.get("score_warnings"), list) else None,
        )
        for run in report.get("runs", [])
    ]
    lines = [
        f"# {_markdown_text(title)}",
        "",
        f"Generated at: `{_markdown_text(report.get('generated_at'))}`",
        "",
        f"Safety note: {_markdown_text(report.get('safety_note'))}",
        "",
        "## Executive Summary",
        "",
        _executive_summary_markdown(report.get("executive_summary")),
        "",
        "## Runs",
        "",
        _table(
            ["Run", "Path", "Strategy", "Total Return", "Ending Balance", "Max Drawdown %", "Overall Score", "Score Warnings"],
            rows,
        ),
        "",
        "## Recommendation",
        "",
        _recommendation_markdown(report.get("recommendation")),
        "",
        "## Rankings",
        "",
    ]
    rankings = report.get("rankings", {})
    if isinstance(rankings, dict):
        for metric in sorted(rankings):
            lines.extend(
                [
                    f"### `{_markdown_text(metric)}`",
                    "",
                    _table(
                        ["Rank", "Run", "Path", "Value", "Available"],
                        [
                            (
                                item.get("rank"),
                                item.get("run_name"),
                                item.get("run_path"),
                                item.get("value"),
                                item.get("available"),
                            )
                            for item in rankings.get(metric, [])
                        ],
                    ),
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def load_comparison_json(path: str | Path) -> dict[str, Any]:
    comparison_path = Path(path)
    if not comparison_path.exists():
        raise BacktestComparisonReportError(f"comparison JSON does not exist: {comparison_path}")
    if not comparison_path.is_file():
        raise BacktestComparisonReportError(f"comparison JSON path is not a file: {comparison_path}")
    try:
        payload = json.loads(comparison_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BacktestComparisonReportError(f"comparison JSON is not valid JSON: {comparison_path}") from exc
    if not isinstance(payload, dict):
        raise BacktestComparisonReportError(f"comparison JSON must contain a JSON object: {comparison_path}")
    return payload


def _report_run(item: dict[str, Any], *, artifact_root: Path | None) -> dict[str, Any]:
    run_dir = item.get("run_dir") or item.get("run_path")
    summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
    payload = {
        "run_name": item.get("run_name"),
        "run_path": _safe_run_path(run_dir, artifact_root=artifact_root),
        "summary": {field: summary.get(field) for field in SUMMARY_FIELDS if field in summary},
        "overall_score": item.get("overall_score") or summary.get("overall_score"),
        "score_components": item.get("score_components") if isinstance(item.get("score_components"), dict) else {},
        "score_warnings": item.get("score_warnings") if isinstance(item.get("score_warnings"), list) else [],
    }
    artifacts = item.get("artifacts")
    if isinstance(artifacts, dict):
        payload["artifacts"] = artifacts
    return payload


def _runs_with_overall_scores_from_rankings(runs: list[Any], rankings: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(rankings.get("overall_score"), list):
        return [item for item in runs if isinstance(item, dict)]
    scores_by_name = {
        item.get("run_name"): item.get("value")
        for item in rankings.get("overall_score", [])
        if isinstance(item, dict) and item.get("available") is True
    }
    hydrated = []
    for item in runs:
        if not isinstance(item, dict):
            continue
        payload = dict(item)
        summary = dict(payload.get("summary")) if isinstance(payload.get("summary"), dict) else {}
        score = payload.get("overall_score") or summary.get("overall_score") or scores_by_name.get(payload.get("run_name"))
        if score is not None:
            payload["overall_score"] = score
            summary["overall_score"] = score
            payload["summary"] = summary
        hydrated.append(payload)
    return hydrated


def _report_rankings(rankings: dict[str, Any], *, artifact_root: Path | None) -> dict[str, list[dict[str, Any]]]:
    return {
        metric: [_report_ranking_item(item, artifact_root=artifact_root) for item in items]
        for metric, items in rankings.items()
        if isinstance(items, list)
    }


def _report_ranking_item(item: dict[str, Any], *, artifact_root: Path | None) -> dict[str, Any]:
    return {
        "rank": item.get("rank"),
        "run_name": item.get("run_name"),
        "run_path": _safe_run_path(item.get("run_dir") or item.get("run_path"), artifact_root=artifact_root),
        "metric": item.get("metric"),
        "value": item.get("value"),
        "available": item.get("available"),
        **({"reason": item.get("reason")} if item.get("reason") else {}),
    }


def _report_recommendation(recommendation: dict[str, Any], *, artifact_root: Path | None) -> dict[str, Any]:
    payload = dict(recommendation)
    recommended_run = recommendation.get("recommended_run")
    if isinstance(recommended_run, dict):
        payload["recommended_run"] = _report_recommendation_run(recommended_run, artifact_root=artifact_root)
    else:
        payload["recommended_run"] = None
    runner_up_runs = recommendation.get("runner_up_runs")
    payload["runner_up_runs"] = [
        _report_recommendation_run(item, artifact_root=artifact_root)
        for item in runner_up_runs
        if isinstance(item, dict)
    ] if isinstance(runner_up_runs, list) else []
    return payload


def _report_recommendation_run(item: dict[str, Any], *, artifact_root: Path | None) -> dict[str, Any]:
    payload = dict(item)
    path_value = item.get("run_dir") or item.get("run_path")
    if path_value not in (None, ""):
        payload["run_path"] = _safe_run_path(path_value, artifact_root=artifact_root)
    payload.pop("run_dir", None)
    return payload


def _recommendation_markdown(recommendation: Any) -> str:
    if not isinstance(recommendation, dict):
        return "Unavailable"
    recommended_run = recommendation.get("recommended_run")
    selected_rows = []
    if isinstance(recommended_run, dict):
        selected_rows.append(
            (
                recommended_run.get("run_name"),
                recommended_run.get("run_path"),
                recommended_run.get("strategy"),
                recommended_run.get("overall_score"),
                recommended_run.get("total_return_pct"),
                recommended_run.get("max_drawdown_pct") or recommended_run.get("max_drawdown_amount"),
                ", ".join(recommended_run.get("score_warnings", [])) if isinstance(recommended_run.get("score_warnings"), list) else None,
            )
        )
    lines = [
        f"Status: `{_markdown_text(recommendation.get('recommendation_status'))}`",
        "",
        _table(
            ["Run", "Path", "Strategy", "Overall Score", "Total Return %", "Drawdown", "Score Warnings"],
            selected_rows,
        ),
        "",
        _table(
            ["Reason", "Value"],
            [
                (key, value)
                for key, value in (recommendation.get("recommendation_reason") or {}).items()
            ] if isinstance(recommendation.get("recommendation_reason"), dict) else [],
        ),
        "",
        _table(
            ["Recommendation Warnings"],
            [(warning,) for warning in recommendation.get("recommendation_warnings", [])]
            if isinstance(recommendation.get("recommendation_warnings"), list) else [],
        ),
        "",
        f"Acceptance status: `{_markdown_text(recommendation.get('acceptance_status'))}`",
        "",
        _table(
            ["Gate", "Passed", "Actual", "Threshold", "Severity", "Reason"],
            [
                (
                    gate.get("name"),
                    gate.get("passed"),
                    gate.get("actual"),
                    gate.get("threshold"),
                    gate.get("severity"),
                    gate.get("reason"),
                )
                for gate in recommendation.get("acceptance_gates", [])
                if isinstance(gate, dict)
            ] if isinstance(recommendation.get("acceptance_gates"), list) else [],
        ),
        "",
        _table(
            ["Acceptance Failures"],
            [(failure,) for failure in recommendation.get("acceptance_failures", [])]
            if isinstance(recommendation.get("acceptance_failures"), list) else [],
        ),
        "",
        _table(
            ["Acceptance Warnings"],
            [(warning,) for warning in recommendation.get("acceptance_warnings", [])]
            if isinstance(recommendation.get("acceptance_warnings"), list) else [],
        ),
    ]
    return "\n".join(lines)


def _executive_summary_markdown(executive_summary: Any) -> str:
    if not isinstance(executive_summary, dict):
        return "Unavailable"
    return _table(
        ["Field", "Value"],
        [
            ("Title", executive_summary.get("title")),
            ("Decision", executive_summary.get("decision")),
            ("Best Strategy", executive_summary.get("best_strategy")),
            ("Best Run", executive_summary.get("best_run_label")),
            ("Acceptance Status", executive_summary.get("acceptance_status")),
            ("Recommendation Status", executive_summary.get("recommendation_status")),
            ("Overall Score", executive_summary.get("overall_score")),
            ("Key Strengths", ", ".join(executive_summary.get("key_strengths", [])) if isinstance(executive_summary.get("key_strengths"), list) else None),
            ("Key Risks", ", ".join(executive_summary.get("key_risks", [])) if isinstance(executive_summary.get("key_risks"), list) else None),
            ("Next Action", executive_summary.get("next_action")),
            ("Summary", executive_summary.get("summary_text")),
        ],
    )


def _safe_run_path(value: Any, *, artifact_root: Path | None) -> str | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    if artifact_root is None:
        return path.as_posix()
    try:
        return path.resolve().relative_to(artifact_root).as_posix()
    except (OSError, ValueError):
        return path.name


def _table(headers: list[str], rows: list[tuple[Any, ...]]) -> str:
    rendered = [
        "| " + " | ".join(_markdown_text(header) for header in headers) + " |",
        "| " + " | ".join("---" for _header in headers) + " |",
    ]
    for row in rows:
        rendered.append("| " + " | ".join(_markdown_text(cell) for cell in row) + " |")
    return "\n".join(rendered)


def _markdown_text(value: Any) -> str:
    if value in (None, ""):
        return "Unavailable"
    return str(value).replace("|", "\\|").replace("\n", " ")
