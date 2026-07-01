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
