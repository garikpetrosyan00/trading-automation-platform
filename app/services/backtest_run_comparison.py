import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class BacktestRunComparisonError(ValueError):
    pass


METRICS = (
    "total_return",
    "final_equity",
    "ending_balance",
    "final_balance",
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
    "fees_paid",
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
    "initial_balance",
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


def compare_backtest_run_dirs(base_run_dir: str | Path, candidate_run_dir: str | Path) -> dict[str, Any]:
    base_dir = Path(base_run_dir)
    candidate_dir = Path(candidate_run_dir)
    base_summary = _load_enriched_summary(base_dir)
    candidate_summary = _load_enriched_summary(candidate_dir)

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


def compare_backtest_run_dirs_many(run_dirs: list[str | Path]) -> dict[str, Any]:
    if len(run_dirs) < 2:
        raise BacktestRunComparisonError("at least two run directories are required")

    run_items = []
    for run_dir in run_dirs:
        path = Path(run_dir)
        summary = _load_enriched_summary(path)
        score = _score_summary(summary)
        summary["overall_score"] = score["overall_score"]
        run_items.append(
            {
                "run_name": path.name,
                "run_dir": str(path),
                "summary": _comparison_summary(path.name, summary),
                "overall_score": score["overall_score"],
                "score_components": score["score_components"],
                "score_warnings": score["score_warnings"],
                "artifacts": _artifact_summary(path),
            }
        )
    run_items.sort(key=_overall_score_sort_key)

    recommendation = build_backtest_recommendation_summary(run_items)
    return {
        "result": "PASS",
        "runs_count": len(run_items),
        "ranking_metrics": ["overall_score", "total_return", "ending_balance", "max_drawdown_pct"],
        "runs": run_items,
        "rankings": {
            "overall_score": _rank_run_items_by_overall_score(run_items),
            "total_return": _rank_run_items(run_items, metric="total_return", higher_is_better=True),
            "ending_balance": _rank_run_items(run_items, metric="ending_balance", higher_is_better=True),
            "max_drawdown_pct": _rank_run_items(run_items, metric="max_drawdown_pct", higher_is_better=False),
        },
        "recommendation": recommendation,
        "executive_summary": build_backtest_executive_summary(recommendation),
    }


def compare_backtest_summaries(
    *,
    base_summary_path: str | Path,
    candidate_summary_path: str | Path,
) -> dict[str, Any]:
    base_path = Path(base_summary_path)
    candidate_path = Path(candidate_summary_path)
    base_summary = _enrich_summary(_load_summary_file(base_path, label="base summary"))
    candidate_summary = _enrich_summary(_load_summary_file(candidate_path, label="candidate summary"))

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
    if "rankings" in report:
        return {
            "result": report["result"],
            "runs_count": report["runs_count"],
            "ranking_metrics": report["ranking_metrics"],
            "rankings": report["rankings"],
            "recommendation": report.get("recommendation"),
            "executive_summary": report.get("executive_summary"),
        }
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


def _load_enriched_summary(run_dir: Path) -> dict[str, Any]:
    return _enrich_summary(_load_summary(run_dir), run_dir=run_dir)


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


def _enrich_summary(summary: dict[str, Any], *, run_dir: Path | None = None) -> dict[str, Any]:
    enriched = dict(summary)
    if "starting_balance" not in enriched and enriched.get("initial_balance") not in (None, ""):
        enriched["starting_balance"] = enriched.get("initial_balance")
    if "ending_balance" not in enriched:
        if enriched.get("final_equity") not in (None, ""):
            enriched["ending_balance"] = enriched.get("final_equity")
        elif enriched.get("final_balance") not in (None, ""):
            enriched["ending_balance"] = enriched.get("final_balance")
    if "total_return" not in enriched:
        total_return = _optional_decimal_delta(enriched.get("starting_balance"), enriched.get("ending_balance"))
        if total_return is not None:
            enriched["total_return"] = _decimal_to_string(total_return)

    if run_dir is not None:
        _enrich_from_trade_rows(enriched, run_dir / "trades.csv")
        _enrich_from_equity_rows(enriched, run_dir / "equity_curve.csv")
    if "total_return" not in enriched:
        total_return = _optional_decimal_delta(enriched.get("starting_balance"), enriched.get("ending_balance"))
        if total_return is not None:
            enriched["total_return"] = _decimal_to_string(total_return)
    return enriched


def _enrich_from_trade_rows(summary: dict[str, Any], path: Path) -> None:
    if not path.is_file():
        return
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return

    if "trades_count" not in summary:
        summary["trades_count"] = len(rows)
    sell_rows = [row for row in rows if str(row.get("side", "")).lower() == "sell"]
    if "completed_round_trips" not in summary:
        summary["completed_round_trips"] = len(sell_rows)
    realized_values = [_optional_decimal(row.get("realized_pnl")) for row in sell_rows]
    numeric_realized_values = [value for value in realized_values if value is not None]
    if sell_rows and len(numeric_realized_values) != len(sell_rows):
        return
    if numeric_realized_values and "realized_pnl" not in summary:
        summary["realized_pnl"] = _decimal_to_string(sum(numeric_realized_values, Decimal("0")))
    if numeric_realized_values:
        winning_values = [value for value in numeric_realized_values if value > 0]
        losing_values = [value for value in numeric_realized_values if value < 0]
        win_count = len(winning_values)
        loss_count = len(losing_values)
        breakeven_count = sum(1 for value in numeric_realized_values if value == 0)
        if "win_count" not in summary:
            summary["win_count"] = win_count
        if "loss_count" not in summary:
            summary["loss_count"] = loss_count
        if "breakeven_count" not in summary:
            summary["breakeven_count"] = breakeven_count
        if "win_rate_pct" not in summary and sell_rows:
            summary["win_rate_pct"] = _decimal_to_string((Decimal(win_count) / Decimal(len(sell_rows))) * Decimal("100"))
        if "average_winning_trade_pnl" not in summary:
            summary["average_winning_trade_pnl"] = _average_decimal_string(winning_values)
        if "average_losing_trade_pnl" not in summary:
            summary["average_losing_trade_pnl"] = _average_decimal_string(losing_values)
        if "average_trade_pnl" not in summary:
            summary["average_trade_pnl"] = _average_decimal_string(numeric_realized_values)
        if "best_trade_pnl" not in summary:
            summary["best_trade_pnl"] = _decimal_to_string(max(numeric_realized_values))
        if "worst_trade_pnl" not in summary:
            summary["worst_trade_pnl"] = _decimal_to_string(min(numeric_realized_values))
        if "profit_factor" not in summary:
            gross_winning_pnl = sum(winning_values, Decimal("0"))
            gross_losing_pnl = abs(sum(losing_values, Decimal("0")))
            summary["profit_factor"] = _profit_factor_string(gross_winning_pnl, gross_losing_pnl)


def _enrich_from_equity_rows(summary: dict[str, Any], path: Path) -> None:
    if not path.is_file():
        return
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return
    equity_values = [_optional_decimal(row.get("equity")) for row in rows]
    equity_values = [value for value in equity_values if value is not None]
    if not equity_values:
        return
    if "ending_balance" not in summary:
        summary["ending_balance"] = _decimal_to_string(equity_values[-1])
    if "final_equity" not in summary:
        summary["final_equity"] = _decimal_to_string(equity_values[-1])
    if "max_drawdown_pct" not in summary:
        max_drawdown = _max_drawdown_pct(equity_values)
        if max_drawdown is not None:
            summary["max_drawdown_pct"] = _decimal_to_string(max_drawdown)
    if "max_drawdown_amount" not in summary:
        max_drawdown_amount = _max_drawdown_amount(equity_values)
        if max_drawdown_amount is not None:
            summary["max_drawdown_amount"] = _decimal_to_string(max_drawdown_amount)
    if "exposure_pct" not in summary:
        position_values = [_optional_decimal(row.get("position_quantity")) for row in rows]
        if position_values and all(value is not None for value in position_values):
            exposure_points = sum(1 for value in position_values if value is not None and value > 0)
            summary["exposure_pct"] = _decimal_to_string((Decimal(exposure_points) / Decimal(len(position_values))) * Decimal("100"))


def _comparison_summary(run_name: str, summary: dict[str, Any]) -> dict[str, Any]:
    payload = {"run_name": run_name}
    payload.update({field: _json_value(summary.get(field)) for field in SUMMARY_FIELDS if field in summary})
    return payload


def build_backtest_recommendation_summary(run_items: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [
        item
        for item in run_items
        if _optional_decimal(item.get("overall_score") or item.get("summary", {}).get("overall_score")) is not None
    ]
    if not comparable:
        recommendation = {
            "recommended_run": None,
            "recommendation_status": "no_valid_runs",
            "recommendation_reason": {
                "highest_overall_score": False,
                "positive_return": False,
                "acceptable_drawdown": False,
                "sufficient_trades": False,
                "better_risk_adjusted_profile": False,
                "score_gap_to_runner_up": None,
            },
            "recommendation_warnings": ["all_runs_weak"],
            "runner_up_runs": [],
        }
        recommendation.update(build_backtest_acceptance_evaluation(recommendation))
        return recommendation

    ranked = sorted(comparable, key=_overall_score_sort_key)
    best = ranked[0]
    runner_ups = ranked[1:3]
    best_score = _optional_decimal(best.get("overall_score") or best.get("summary", {}).get("overall_score")) or Decimal("0")
    runner_up_score = (
        _optional_decimal(runner_ups[0].get("overall_score") or runner_ups[0].get("summary", {}).get("overall_score"))
        if runner_ups
        else None
    )
    score_gap = best_score - runner_up_score if runner_up_score is not None else None
    summary = best.get("summary", {}) if isinstance(best.get("summary"), dict) else {}
    selected_warnings = _string_list(best.get("score_warnings"))
    severe_warnings = {"no_trades", "negative_return", "high_drawdown"}
    recommendation_warnings = list(selected_warnings)
    if best_score < Decimal("50"):
        recommendation_warnings.append("best_run_has_low_score")
    if "too_few_trades" in selected_warnings:
        recommendation_warnings.append("best_run_has_too_few_trades")
    if "high_drawdown" in selected_warnings:
        recommendation_warnings.append("best_run_has_high_drawdown")
    if "negative_return" in selected_warnings:
        recommendation_warnings.append("best_run_has_negative_return")
    if "no_trades" in selected_warnings:
        recommendation_warnings.append("best_run_has_no_trades")
    if len(ranked) > 1 and score_gap is not None and score_gap < Decimal("5"):
        recommendation_warnings.append("no_clear_winner")

    has_severe_warning = any(warning in selected_warnings for warning in severe_warnings)
    all_runs_weak = all(
        (_optional_decimal(item.get("overall_score") or item.get("summary", {}).get("overall_score")) or Decimal("0")) < Decimal("70")
        for item in ranked
    )
    if all_runs_weak:
        recommendation_warnings.append("all_runs_weak")

    if (
        best_score >= Decimal("70")
        and not has_severe_warning
        and "too_few_trades" not in selected_warnings
        and "no_clear_winner" not in recommendation_warnings
    ):
        status = "recommended"
    elif best_score >= Decimal("50") and not has_severe_warning:
        status = "weak_recommendation"
    else:
        status = "not_recommended"

    reason = {
        "highest_overall_score": True,
        "positive_return": (_optional_decimal(summary.get("total_return_pct")) or _optional_decimal(summary.get("total_return")) or Decimal("0")) > 0,
        "acceptable_drawdown": (_optional_decimal(summary.get("max_drawdown_pct")) or Decimal("0")) < Decimal("20"),
        "sufficient_trades": (_optional_decimal(summary.get("completed_round_trips")) or Decimal("0")) >= Decimal("5"),
        "better_risk_adjusted_profile": status in {"recommended", "weak_recommendation"} and "no_clear_winner" not in recommendation_warnings,
        "score_gap_to_runner_up": _decimal_to_string(score_gap) if score_gap is not None else None,
    }

    recommendation = {
        "recommended_run": _recommendation_run(best),
        "recommendation_status": status,
        "recommendation_reason": reason,
        "recommendation_warnings": sorted(set(recommendation_warnings)),
        "runner_up_runs": [_recommendation_run(item) for item in runner_ups],
    }
    recommendation.update(build_backtest_acceptance_evaluation(recommendation))
    return recommendation


def build_backtest_acceptance_evaluation(recommendation: dict[str, Any]) -> dict[str, Any]:
    recommended_run = recommendation.get("recommended_run")
    if not isinstance(recommended_run, dict):
        return {
            "acceptance_status": "not_evaluated",
            "acceptance_gates": [],
            "acceptance_failures": ["no_valid_recommended_run"],
            "acceptance_warnings": [],
        }

    gates: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []
    recommendation_status = recommendation.get("recommendation_status")
    recommendation_warnings = _string_list(recommendation.get("recommendation_warnings"))
    score_warnings = _string_list(recommended_run.get("score_warnings"))

    _add_gate(
        gates,
        failures=failures,
        warnings=warnings,
        name="recommendation_status",
        passed=recommendation_status in {"recommended", "weak_recommendation"},
        actual=recommendation_status,
        threshold="recommended_or_weak_recommendation",
        severity="failure",
        code="recommendation_not_strong_enough",
        reason="recommendation_status must be recommended or weak_recommendation",
    )
    if recommendation_status == "weak_recommendation":
        _add_gate(
            gates,
            failures=failures,
            warnings=warnings,
            name="weak_recommendation_only",
            passed=True,
            actual=recommendation_status,
            threshold="recommended",
            severity="warning",
            code="weak_recommendation_only",
            reason="best run is only weakly recommended",
        )

    overall_score = _optional_decimal(recommended_run.get("overall_score"))
    _add_numeric_min_gate(
        gates,
        failures=failures,
        warnings=warnings,
        name="minimum_overall_score",
        actual=overall_score,
        threshold=Decimal("70"),
        code="score_below_minimum",
        reason="overall_score must be at least 70",
    )
    trade_count = _optional_decimal(recommended_run.get("trade_count"))
    _add_numeric_min_gate(
        gates,
        failures=failures,
        warnings=warnings,
        name="minimum_trade_count",
        actual=trade_count,
        threshold=Decimal("5"),
        code="too_few_trades",
        reason="trade_count must be at least 5",
    )
    if trade_count is not None and trade_count < Decimal("10"):
        _add_gate(
            gates,
            failures=failures,
            warnings=warnings,
            name="trade_confidence",
            passed=True,
            actual=_decimal_to_string(trade_count),
            threshold="10",
            severity="warning",
            code="low_trade_confidence",
            reason="trade_count is acceptable but still low-confidence",
        )

    total_return_pct = _optional_decimal(recommended_run.get("total_return_pct"))
    _add_gate(
        gates,
        failures=failures,
        warnings=warnings,
        name="minimum_total_return_pct",
        passed=total_return_pct is not None and total_return_pct > 0,
        actual=_decimal_to_string(total_return_pct) if total_return_pct is not None else None,
        threshold=">0",
        severity="failure",
        code="non_positive_return",
        reason="total_return_pct must be positive",
    )

    max_drawdown_pct = _optional_decimal(recommended_run.get("max_drawdown_pct"))
    if max_drawdown_pct is None:
        _add_gate(
            gates,
            failures=failures,
            warnings=warnings,
            name="maximum_drawdown_pct",
            passed=True,
            actual=None,
            threshold="25",
            severity="warning",
            code="missing_drawdown_metric",
            reason="max_drawdown_pct is unavailable",
        )
    else:
        _add_gate(
            gates,
            failures=failures,
            warnings=warnings,
            name="maximum_drawdown_pct",
            passed=max_drawdown_pct <= Decimal("25"),
            actual=_decimal_to_string(max_drawdown_pct),
            threshold="25",
            severity="failure",
            code="drawdown_too_high",
            reason="max_drawdown_pct must be at most 25",
        )

    profit_factor = _optional_decimal(recommended_run.get("profit_factor"))
    if profit_factor is None:
        _add_gate(
            gates,
            failures=failures,
            warnings=warnings,
            name="minimum_profit_factor",
            passed=True,
            actual=None,
            threshold="1.1",
            severity="warning",
            code="missing_profit_factor",
            reason="profit_factor is unavailable",
        )
    else:
        _add_gate(
            gates,
            failures=failures,
            warnings=warnings,
            name="minimum_profit_factor",
            passed=profit_factor >= Decimal("1.1"),
            actual=_decimal_to_string(profit_factor),
            threshold="1.1",
            severity="failure",
            code="profit_factor_below_minimum",
            reason="profit_factor must be at least 1.1",
        )

    severe_recommendation_warnings = {
        "best_run_has_low_score",
        "best_run_has_high_drawdown",
        "best_run_has_negative_return",
        "best_run_has_no_trades",
    }
    severe_present = sorted(set(recommendation_warnings).intersection(severe_recommendation_warnings))
    _add_gate(
        gates,
        failures=failures,
        warnings=warnings,
        name="no_severe_recommendation_warnings",
        passed=not severe_present,
        actual=severe_present,
        threshold=[],
        severity="failure",
        code="severe_recommendation_warning",
        reason="recommendation must not include severe warnings",
    )
    _add_gate(
        gates,
        failures=failures,
        warnings=warnings,
        name="no_no_trades_warning",
        passed="no_trades" not in score_warnings and "best_run_has_no_trades" not in recommendation_warnings,
        actual=score_warnings,
        threshold="no no_trades warning",
        severity="failure",
        code="too_few_trades",
        reason="recommended run must not have no_trades warning",
    )
    _add_gate(
        gates,
        failures=failures,
        warnings=warnings,
        name="no_negative_return_warning",
        passed="negative_return" not in score_warnings and "best_run_has_negative_return" not in recommendation_warnings,
        actual=score_warnings,
        threshold="no negative_return warning",
        severity="failure",
        code="negative_return",
        reason="recommended run must not have negative_return warning",
    )
    if "no_clear_winner" in recommendation_warnings:
        _add_gate(
            gates,
            failures=failures,
            warnings=warnings,
            name="clear_winner",
            passed=True,
            actual="no_clear_winner",
            threshold="score_gap_to_runner_up >= 5",
            severity="warning",
            code="no_clear_winner",
            reason="top runs are close in overall_score",
        )

    unique_failures = sorted(set(failures))
    unique_warnings = sorted(set(warnings))
    if unique_failures:
        status = "rejected"
    elif unique_warnings:
        status = "accepted_with_warnings"
    else:
        status = "accepted"
    return {
        "acceptance_status": status,
        "acceptance_gates": gates,
        "acceptance_failures": unique_failures,
        "acceptance_warnings": unique_warnings,
    }


def build_backtest_executive_summary(recommendation: dict[str, Any]) -> dict[str, Any]:
    recommended_run = recommendation.get("recommended_run") if isinstance(recommendation, dict) else None
    recommended_run = recommended_run if isinstance(recommended_run, dict) else {}
    acceptance_status = recommendation.get("acceptance_status") if isinstance(recommendation, dict) else None
    recommendation_status = recommendation.get("recommendation_status") if isinstance(recommendation, dict) else None
    decision = _executive_decision(acceptance_status)
    key_strengths = _executive_key_strengths(recommendation, recommended_run)
    key_risks = _executive_key_risks(recommendation)
    next_action = _executive_next_action(decision, key_risks)
    best_run_label = recommended_run.get("run_name") or recommended_run.get("run_path")
    best_strategy = recommended_run.get("strategy")
    overall_score = recommended_run.get("overall_score")
    return {
        "title": "Local Backtest Comparison Executive Summary",
        "decision": decision,
        "best_strategy": best_strategy,
        "best_run_label": best_run_label,
        "acceptance_status": acceptance_status or "not_evaluated",
        "recommendation_status": recommendation_status or "no_valid_runs",
        "overall_score": overall_score,
        "key_strengths": key_strengths,
        "key_risks": key_risks,
        "next_action": next_action,
        "summary_text": _executive_summary_text(
            decision=decision,
            best_run_label=best_run_label,
            acceptance_status=acceptance_status or "not_evaluated",
            recommendation_status=recommendation_status or "no_valid_runs",
            next_action=next_action,
        ),
    }


def _executive_decision(acceptance_status: Any) -> str:
    return {
        "accepted": "accept_candidate",
        "accepted_with_warnings": "accept_with_warnings",
        "rejected": "reject_candidate",
        "not_evaluated": "no_decision",
    }.get(str(acceptance_status), "no_decision")


def _executive_key_strengths(recommendation: dict[str, Any], recommended_run: dict[str, Any]) -> list[str]:
    reason = recommendation.get("recommendation_reason") if isinstance(recommendation.get("recommendation_reason"), dict) else {}
    strengths = []
    ordered_reason_fields = (
        ("highest_overall_score", "highest_overall_score"),
        ("positive_return", "positive_return"),
        ("acceptable_drawdown", "acceptable_drawdown"),
        ("sufficient_trades", "sufficient_trade_count"),
        ("better_risk_adjusted_profile", "better_risk_adjusted_profile"),
    )
    for field, strength in ordered_reason_fields:
        if reason.get(field) is True:
            strengths.append(strength)
    profit_factor = _optional_decimal(recommended_run.get("profit_factor"))
    if profit_factor is not None and profit_factor >= Decimal("1.1"):
        strengths.append("acceptable_profit_factor")
    return strengths


def _executive_key_risks(recommendation: dict[str, Any]) -> list[str]:
    codes = set(_string_list(recommendation.get("acceptance_failures")))
    codes.update(_string_list(recommendation.get("acceptance_warnings")))
    codes.update(_string_list(recommendation.get("recommendation_warnings")))
    risk_rules = (
        ("too_few_trades", {"too_few_trades", "best_run_has_too_few_trades", "low_trade_confidence"}),
        ("high_drawdown", {"drawdown_too_high", "best_run_has_high_drawdown", "high_drawdown"}),
        ("negative_return", {"negative_return", "non_positive_return", "best_run_has_negative_return"}),
        ("low_score", {"score_below_minimum", "best_run_has_low_score"}),
        ("missing_profit_factor", {"missing_profit_factor", "infinite_or_unavailable_profit_factor"}),
        ("missing_drawdown_metric", {"missing_drawdown_metric"}),
        ("no_clear_winner", {"no_clear_winner"}),
        ("weak_recommendation_only", {"weak_recommendation_only"}),
    )
    return [risk for risk, matching_codes in risk_rules if codes.intersection(matching_codes)]


def _executive_next_action(decision: str, key_risks: list[str]) -> str:
    if decision == "accept_candidate":
        return "promote_to_further_local_testing"
    if decision == "accept_with_warnings":
        data_risks = {"too_few_trades", "missing_profit_factor", "missing_drawdown_metric"}
        if data_risks.intersection(key_risks):
            return "add_more_data_and_rerun"
        return "review_with_caution"
    if decision == "reject_candidate":
        return "reject_or_adjust_strategy"
    return "no_action_available"


def _executive_summary_text(
    *,
    decision: str,
    best_run_label: Any,
    acceptance_status: str,
    recommendation_status: str,
    next_action: str,
) -> str:
    run_label = str(best_run_label) if best_run_label not in (None, "") else "no comparable run"
    return (
        f"Decision {decision} for {run_label}; acceptance_status={acceptance_status}; "
        f"recommendation_status={recommendation_status}; next_action={next_action}."
    )


def _add_numeric_min_gate(
    gates: list[dict[str, Any]],
    *,
    failures: list[str],
    warnings: list[str],
    name: str,
    actual: Decimal | None,
    threshold: Decimal,
    code: str,
    reason: str,
) -> None:
    _add_gate(
        gates,
        failures=failures,
        warnings=warnings,
        name=name,
        passed=actual is not None and actual >= threshold,
        actual=_decimal_to_string(actual) if actual is not None else None,
        threshold=_decimal_to_string(threshold),
        severity="failure",
        code=code,
        reason=reason,
    )


def _add_gate(
    gates: list[dict[str, Any]],
    *,
    failures: list[str],
    warnings: list[str],
    name: str,
    passed: bool,
    actual: Any,
    threshold: Any,
    severity: str,
    code: str,
    reason: str,
) -> None:
    gates.append(
        {
            "name": name,
            "passed": passed,
            "actual": _json_value(actual),
            "threshold": _json_value(threshold),
            "severity": severity,
            "reason": reason,
        }
    )
    if not passed and severity == "failure":
        failures.append(code)
    elif severity == "warning":
        warnings.append(code)


def _recommendation_run(item: dict[str, Any]) -> dict[str, Any]:
    summary = item.get("summary", {}) if isinstance(item.get("summary"), dict) else {}
    return {
        "strategy": summary.get("strategy_type"),
        "run_name": item.get("run_name") or summary.get("run_name"),
        "run_dir": item.get("run_dir"),
        "run_path": item.get("run_path"),
        "overall_score": item.get("overall_score") or summary.get("overall_score"),
        "total_return_pct": summary.get("total_return_pct"),
        "max_drawdown_pct": summary.get("max_drawdown_pct"),
        "max_drawdown_amount": summary.get("max_drawdown_amount"),
        "profit_factor": summary.get("profit_factor"),
        "win_rate": summary.get("win_rate_pct"),
        "trade_count": summary.get("completed_round_trips") if summary.get("completed_round_trips") is not None else summary.get("trades_count"),
        "exposure_pct": summary.get("exposure_pct"),
        "score_warnings": _string_list(item.get("score_warnings")),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _score_summary(summary: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    return_pct = _return_pct(summary, warnings=warnings)
    drawdown_pct = _drawdown_pct(summary, warnings=warnings)
    profit_factor = _profit_factor(summary, warnings=warnings)
    win_rate = _win_rate(summary, warnings=warnings)
    trade_count = _trade_count(summary, warnings=warnings)
    exposure_pct = _exposure_pct(summary, warnings=warnings)

    if return_pct is not None and return_pct < 0:
        warnings.append("negative_return")
    if drawdown_pct is not None and drawdown_pct >= Decimal("20"):
        warnings.append("high_drawdown")
    if trade_count == 0:
        warnings.append("no_trades")
    elif trade_count is not None and trade_count < 5:
        warnings.append("too_few_trades")

    components = {
        "return_score": _score_return(return_pct),
        "drawdown_score": _score_drawdown(drawdown_pct),
        "profit_factor_score": _score_profit_factor(profit_factor),
        "win_rate_score": _score_win_rate(win_rate),
        "trade_count_score": _score_trade_count(trade_count),
        "exposure_score": _score_exposure(exposure_pct),
    }
    overall = (
        components["return_score"] * Decimal("0.30")
        + components["drawdown_score"] * Decimal("0.25")
        + components["profit_factor_score"] * Decimal("0.15")
        + components["win_rate_score"] * Decimal("0.10")
        + components["trade_count_score"] * Decimal("0.15")
        + components["exposure_score"] * Decimal("0.05")
    )
    if "no_trades" in warnings:
        overall = min(overall, Decimal("20"))
    elif "too_few_trades" in warnings:
        overall = min(overall, Decimal("60"))
    components["final_normalized_score"] = _bounded_score(overall)
    return {
        "overall_score": _score_to_string(components["final_normalized_score"]),
        "score_components": {
            key: _score_to_string(value)
            for key, value in components.items()
        },
        "score_warnings": sorted(set(warnings)),
    }


def _return_pct(summary: dict[str, Any], *, warnings: list[str]) -> Decimal | None:
    value = _optional_decimal(summary.get("total_return_pct"))
    if value is not None:
        return value
    total_return = _optional_decimal(summary.get("total_return"))
    starting_balance = _optional_decimal(summary.get("starting_balance") or summary.get("initial_balance"))
    if total_return is not None and starting_balance not in (None, Decimal("0")):
        return (total_return / starting_balance) * Decimal("100")
    warnings.append("missing_metric")
    return None


def _drawdown_pct(summary: dict[str, Any], *, warnings: list[str]) -> Decimal | None:
    value = _optional_decimal(summary.get("max_drawdown_pct"))
    if value is not None:
        return abs(value)
    drawdown_amount = _optional_decimal(summary.get("max_drawdown_amount"))
    starting_balance = _optional_decimal(summary.get("starting_balance") or summary.get("initial_balance"))
    if drawdown_amount is not None and starting_balance not in (None, Decimal("0")):
        return (abs(drawdown_amount) / starting_balance) * Decimal("100")
    warnings.append("missing_metric")
    return None


def _profit_factor(summary: dict[str, Any], *, warnings: list[str]) -> Decimal | None:
    value = _optional_decimal(summary.get("profit_factor"))
    if value is not None:
        return value
    if _optional_decimal(summary.get("win_count")) and _optional_decimal(summary.get("loss_count")) == 0:
        warnings.append("infinite_or_unavailable_profit_factor")
        return Decimal("4")
    warnings.append("infinite_or_unavailable_profit_factor")
    return None


def _win_rate(summary: dict[str, Any], *, warnings: list[str]) -> Decimal | None:
    value = _optional_decimal(summary.get("win_rate_pct"))
    if value is not None:
        return value
    warnings.append("missing_metric")
    return None


def _trade_count(summary: dict[str, Any], *, warnings: list[str]) -> int | None:
    value = _optional_decimal(summary.get("completed_round_trips"))
    if value is None:
        trades_count = _optional_decimal(summary.get("trades_count"))
        if trades_count is not None:
            value = trades_count / Decimal("2")
    if value is None:
        warnings.append("missing_metric")
        return None
    return int(value) if value >= 0 else 0


def _exposure_pct(summary: dict[str, Any], *, warnings: list[str]) -> Decimal | None:
    value = _optional_decimal(summary.get("exposure_pct"))
    if value is None:
        warnings.append("missing_metric")
    return value


def _score_return(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("35")
    return _bounded_score((value + Decimal("20")) * Decimal("2"))


def _score_drawdown(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("50")
    return _bounded_score(Decimal("100") - (value * Decimal("3.333333333333333333333333333")))


def _score_profit_factor(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("35")
    return _bounded_score((value / Decimal("3")) * Decimal("100"))


def _score_win_rate(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("40")
    return _bounded_score(value)


def _score_trade_count(value: int | None) -> Decimal:
    if value is None:
        return Decimal("25")
    return _bounded_score((Decimal(value) / Decimal("10")) * Decimal("100"))


def _score_exposure(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("70")
    return _bounded_score(Decimal("100") - max(Decimal("0"), value - Decimal("80")) * Decimal("2"))


def _bounded_score(value: Decimal) -> Decimal:
    if value < 0:
        return Decimal("0")
    if value > 100:
        return Decimal("100")
    return value


def _score_to_string(value: Decimal) -> str:
    return _decimal_to_string(value.quantize(Decimal("0.0001")))


def _overall_score_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    score = _optional_decimal(item.get("overall_score")) or Decimal("-1")
    total_return = _optional_decimal(item.get("summary", {}).get("total_return_pct"))
    if total_return is None:
        total_return = _optional_decimal(item.get("summary", {}).get("total_return")) or Decimal("-999999999")
    drawdown = _optional_decimal(item.get("summary", {}).get("max_drawdown_pct")) or Decimal("999999999")
    return (-score, -total_return, drawdown, str(item["run_name"]), str(item["run_dir"]))


def _rank_run_items_by_overall_score(run_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked_items = sorted(run_items, key=_overall_score_sort_key)
    return [
        {
            "rank": index,
            "run_name": item["run_name"],
            "run_dir": item["run_dir"],
            "metric": "overall_score",
            "value": item["overall_score"],
            "available": True,
        }
        for index, item in enumerate(ranked_items, start=1)
    ]


def _rank_run_items(
    run_items: list[dict[str, Any]],
    *,
    metric: str,
    higher_is_better: bool,
) -> list[dict[str, Any]]:
    available = []
    unavailable = []
    for item in run_items:
        value = _optional_decimal(item["summary"].get(metric))
        if value is None:
            unavailable.append(
                {
                    "rank": None,
                    "run_name": item["run_name"],
                    "run_dir": item["run_dir"],
                    "metric": metric,
                    "value": None,
                    "available": False,
                    "reason": "metric missing, null, or non-numeric",
                }
            )
        else:
            available.append((item, value))

    available.sort(
        key=lambda pair: (
            -pair[1] if higher_is_better else pair[1],
            str(pair[0]["run_name"]),
            str(pair[0]["run_dir"]),
        )
    )
    ranked = [
        {
            "rank": index,
            "run_name": item["run_name"],
            "run_dir": item["run_dir"],
            "metric": metric,
            "value": _decimal_to_string(value),
            "available": True,
        }
        for index, (item, value) in enumerate(available, start=1)
    ]
    return ranked + sorted(unavailable, key=lambda item: (str(item["run_name"]), str(item["run_dir"])))


def _optional_decimal_delta(start: Any, end: Any) -> Decimal | None:
    start_decimal = _optional_decimal(start)
    end_decimal = _optional_decimal(end)
    if start_decimal is None or end_decimal is None:
        return None
    return end_decimal - start_decimal


def _optional_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _max_drawdown_pct(equity_values: list[Decimal]) -> Decimal | None:
    if not equity_values:
        return None
    peak = equity_values[0]
    max_drawdown = Decimal("0")
    for value in equity_values:
        if value > peak:
            peak = value
        if peak <= 0:
            continue
        drawdown = ((peak - value) / peak) * Decimal("100")
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown


def _max_drawdown_amount(equity_values: list[Decimal]) -> Decimal | None:
    if not equity_values:
        return None
    peak = equity_values[0]
    max_drawdown = Decimal("0")
    for value in equity_values:
        if value > peak:
            peak = value
        drawdown = peak - value
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown


def _average_decimal_string(values: list[Decimal]) -> str | None:
    if not values:
        return None
    return _decimal_to_string(sum(values, Decimal("0")) / Decimal(len(values)))


def _profit_factor_string(gross_winning_pnl: Decimal, gross_losing_pnl: Decimal) -> str | None:
    if gross_losing_pnl > 0:
        return _decimal_to_string(gross_winning_pnl / gross_losing_pnl)
    return None


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
