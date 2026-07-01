import csv
import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.cli.run_backtest import _summary_payload, _to_jsonable, _write_output_dir
from app.services.backtest_run_comparison import (
    _artifact_summary,
    _comparison_summary,
    _load_enriched_summary,
    _rank_run_items,
    _rank_run_items_by_overall_score,
    _score_summary,
    build_backtest_executive_summary,
    build_backtest_recommendation_summary,
)
from app.services.csv_backtest import CsvBacktestCandle, run_csv_backtest


class BacktestParameterSweepError(ValueError):
    pass


SWEEP_RESULT_FIELDS = [
    "rank",
    "run_name",
    "entry_below",
    "exit_above",
    "final_equity",
    "total_return_pct",
    "trades_count",
    "win_rate_pct",
    "max_drawdown_pct",
    "fees_paid",
    "overall_score",
    "acceptance_status",
    "score_warnings",
    "summary_path",
]


def run_backtest_parameter_sweep(
    *,
    candles: list[CsvBacktestCandle],
    symbol: str,
    timeframe: str,
    initial_balance: Decimal,
    fee_rate: Decimal,
    strategy_type: str,
    entry_below_values: list[Decimal],
    exit_above_values: list[Decimal],
    order_quantity: Decimal,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    if strategy_type != "price_threshold":
        raise BacktestParameterSweepError(f"unsupported strategy type: {strategy_type}")
    if not entry_below_values:
        raise BacktestParameterSweepError("at least one entry threshold is required")
    if not exit_above_values:
        raise BacktestParameterSweepError("at least one exit threshold is required")

    destination = Path(output_dir)
    _prepare_output_dir(destination, overwrite=overwrite)

    results: list[dict[str, Any]] = []
    combinations = [
        (entry_below, exit_above)
        for entry_below in entry_below_values
        for exit_above in exit_above_values
    ]
    for index, (entry_below, exit_above) in enumerate(combinations, start=1):
        run_name = f"run_{index:03d}_entry_{_slug_decimal(entry_below)}_exit_{_slug_decimal(exit_above)}"
        run_dir = destination / run_name
        result = run_csv_backtest(
            candles=candles,
            symbol=symbol,
            timeframe=timeframe,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            strategy_type=strategy_type,
            parameters={
                "buy_below": entry_below,
                "sell_above": exit_above,
                "quantity": order_quantity,
            },
        )
        full_payload = _to_jsonable(result)
        summary_payload = _summary_payload(full_payload)
        summary_payload.update(
            {
                "strategy_type": strategy_type,
                "entry_below": _decimal_to_string(entry_below),
                "exit_above": _decimal_to_string(exit_above),
                "order_quantity": _decimal_to_string(order_quantity),
                "fee_rate": _decimal_to_string(fee_rate),
            }
        )
        _write_output_dir(run_dir, full_payload, summary_payload, overwrite=True)
        results.append(_result_row(run_name, run_dir, summary_payload))

    comparison = _sweep_comparison_from_run_dirs([destination / result["run_name"] for result in results])
    results = _enrich_results_with_comparison(results, comparison)
    ranked_results = _rank_results(results)
    sweep_summary = {
        "result": "PASS",
        "symbol": symbol.strip().upper(),
        "timeframe": timeframe.strip(),
        "strategy_type": strategy_type,
        "initial_balance": _decimal_to_string(initial_balance),
        "fee_rate": _decimal_to_string(fee_rate),
        "order_quantity": _decimal_to_string(order_quantity),
        "combinations_count": len(ranked_results),
        "ranking_metric": "final_equity",
        "profitability_note": "Historical local simulation only; not a profitability guarantee.",
        "best_result": ranked_results[0] if ranked_results else None,
        "sweep_summary": build_sweep_scoring_summary(comparison),
        "results": ranked_results,
    }
    (destination / "sweep_summary.json").write_text(json.dumps(sweep_summary, sort_keys=True) + "\n", encoding="utf-8")
    _write_results_csv(destination / "sweep_results.csv", ranked_results)
    (destination / "sweep_report.md").write_text(_sweep_report_markdown(sweep_summary), encoding="utf-8")
    return sweep_summary


def compact_sweep_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "result": summary["result"],
        "symbol": summary["symbol"],
        "timeframe": summary["timeframe"],
        "strategy_type": summary["strategy_type"],
        "combinations_count": summary["combinations_count"],
        "ranking_metric": summary["ranking_metric"],
        "best_result": summary["best_result"],
        "sweep_summary": summary.get("sweep_summary"),
        "lifecycle_closeout": summary.get("lifecycle_closeout"),
    }


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise BacktestParameterSweepError(f"output-dir points to a file: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise BacktestParameterSweepError(f"output directory is not empty; pass --overwrite to replace: {output_dir}")
        for child in output_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)


def _result_row(run_name: str, run_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": None,
        "run_name": run_name,
        "entry_below": summary.get("entry_below"),
        "exit_above": summary.get("exit_above"),
        "final_equity": _available(summary.get("final_equity")),
        "total_return_pct": _available(summary.get("total_return_pct")),
        "trades_count": _available(summary.get("trades_count")),
        "win_rate_pct": _available(summary.get("win_rate_pct")),
        "max_drawdown_pct": _available(summary.get("max_drawdown_pct")),
        "fees_paid": _available(summary.get("fees_paid")),
        "overall_score": _available(summary.get("overall_score")),
        "acceptance_status": "Unavailable",
        "score_warnings": "",
        "summary_path": str(run_dir / "summary.json"),
    }


def _rank_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        results,
        key=lambda item: (
            -_decimal_sort_value(item.get("final_equity")),
            -_decimal_sort_value(item.get("total_return_pct")),
            _decimal_sort_value(item.get("max_drawdown_pct")),
            _decimal_sort_value(item.get("entry_below")),
            _decimal_sort_value(item.get("exit_above")),
            str(item.get("run_name")),
        ),
    )
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return ranked


def _write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SWEEP_RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in SWEEP_RESULT_FIELDS})


def _sweep_report_markdown(summary: dict[str, Any]) -> str:
    rows = "\n".join(
        "| "
        + " | ".join(str(result.get(field, "Unavailable")) for field in ["rank", "run_name", "entry_below", "exit_above", "final_equity", "total_return_pct"])
        + " |"
        for result in summary["results"]
    )
    return (
        "# Backtest Parameter Sweep\n\n"
        "Safety note: local CSV simulation only. This is not live/testnet execution and is not a profitability guarantee.\n\n"
        f"- Symbol: `{summary['symbol']}`\n"
        f"- Timeframe: `{summary['timeframe']}`\n"
        f"- Strategy: `{summary['strategy_type']}`\n"
        f"- Combinations: `{summary['combinations_count']}`\n"
        f"- Ranking metric: `{summary['ranking_metric']}`\n\n"
        f"## Sweep Summary\n\n"
        f"- Best overall score: `{_markdown_value(summary.get('sweep_summary', {}).get('best_overall_score'))}`\n"
        f"- Recommendation status: `{_markdown_value(summary.get('sweep_summary', {}).get('recommendation_status'))}`\n"
        f"- Acceptance status: `{_markdown_value(summary.get('sweep_summary', {}).get('acceptance_status'))}`\n"
        f"- Executive decision: `{_markdown_value(summary.get('sweep_summary', {}).get('executive_decision'))}`\n"
        f"- Accepted parameter sets: `{_markdown_value(summary.get('sweep_summary', {}).get('accepted_count'))}`\n"
        f"- Rejected parameter sets: `{_markdown_value(summary.get('sweep_summary', {}).get('rejected_count'))}`\n"
        f"- Warnings: `{', '.join(summary.get('sweep_summary', {}).get('warnings', [])) or 'none'}`\n\n"
        "| Rank | Run | Entry Below | Exit Above | Final Equity | Total Return % |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"{rows}\n"
    )


def build_sweep_scoring_summary(comparison: dict[str, Any], *, top_limit: int = 3) -> dict[str, Any]:
    runs = comparison.get("runs") if isinstance(comparison, dict) else None
    if not isinstance(runs, list) or not runs:
        return {
            "best_parameter_set": None,
            "best_overall_score": None,
            "recommendation_status": "no_valid_runs",
            "acceptance_status": "not_evaluated",
            "executive_decision": "no_decision",
            "tested_parameter_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "warning_count": 1,
            "top_parameter_sets": [],
            "warnings": ["no_parameter_sets_tested"],
        }

    ranked_runs = sorted(runs, key=_sweep_run_sort_key)
    top_parameter_sets = [_parameter_set_summary(run) for run in ranked_runs[:top_limit]]
    best_parameter_set = top_parameter_sets[0] if top_parameter_sets else None
    recommendation = comparison.get("recommendation") if isinstance(comparison.get("recommendation"), dict) else {}
    executive_summary = (
        comparison.get("executive_summary")
        if isinstance(comparison.get("executive_summary"), dict)
        else build_backtest_executive_summary(recommendation)
    )
    parameter_acceptance = [_parameter_acceptance(run) for run in ranked_runs]
    accepted_count = sum(1 for status in parameter_acceptance if status in {"accepted", "accepted_with_warnings"})
    rejected_count = sum(1 for status in parameter_acceptance if status == "rejected")
    warnings = _sweep_warnings(ranked_runs, accepted_count=accepted_count)

    return {
        "best_parameter_set": best_parameter_set,
        "best_overall_score": best_parameter_set.get("overall_score") if best_parameter_set else None,
        "recommendation_status": recommendation.get("recommendation_status", "no_valid_runs"),
        "acceptance_status": recommendation.get("acceptance_status", "not_evaluated"),
        "executive_decision": executive_summary.get("decision", "no_decision"),
        "tested_parameter_count": len(ranked_runs),
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "warning_count": len(warnings),
        "top_parameter_sets": top_parameter_sets,
        "warnings": warnings,
    }


def _sweep_comparison_from_run_dirs(run_dirs: list[Path]) -> dict[str, Any]:
    run_items = []
    for run_dir in run_dirs:
        summary = _load_enriched_summary(run_dir)
        score = _score_summary(summary)
        summary["overall_score"] = score["overall_score"]
        run_items.append(
            {
                "run_name": run_dir.name,
                "run_dir": str(run_dir),
                "summary": _comparison_summary(run_dir.name, summary),
                "overall_score": score["overall_score"],
                "score_components": score["score_components"],
                "score_warnings": score["score_warnings"],
                "artifacts": _artifact_summary(run_dir),
            }
        )
    run_items = sorted(run_items, key=_sweep_run_sort_key)
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


def _enrich_results_with_comparison(results: list[dict[str, Any]], comparison: dict[str, Any]) -> list[dict[str, Any]]:
    runs_by_name = {
        run.get("run_name"): run
        for run in comparison.get("runs", [])
        if isinstance(run, dict) and isinstance(run.get("run_name"), str)
    }
    enriched = []
    for result in results:
        run = runs_by_name.get(result.get("run_name"))
        if isinstance(run, dict):
            result = dict(result)
            result["overall_score"] = _available(run.get("overall_score"))
            result["acceptance_status"] = _parameter_acceptance(run)
            warnings = run.get("score_warnings") if isinstance(run.get("score_warnings"), list) else []
            result["score_warnings"] = ",".join(warnings)
        enriched.append(result)
    return enriched


def _parameter_set_summary(run: dict[str, Any]) -> dict[str, Any]:
    summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    return {
        "strategy": summary.get("strategy_type"),
        "parameters": {
            "entry_below": summary.get("entry_below"),
            "exit_above": summary.get("exit_above"),
            "order_quantity": summary.get("order_quantity"),
        },
        "overall_score": run.get("overall_score") or summary.get("overall_score"),
        "total_return_pct": summary.get("total_return_pct"),
        "max_drawdown_pct": summary.get("max_drawdown_pct"),
        "max_drawdown_amount": summary.get("max_drawdown_amount"),
        "profit_factor": summary.get("profit_factor"),
        "win_rate": summary.get("win_rate_pct"),
        "trade_count": summary.get("completed_round_trips") if summary.get("completed_round_trips") is not None else summary.get("trades_count"),
        "score_warnings": run.get("score_warnings") if isinstance(run.get("score_warnings"), list) else [],
        "acceptance_status": _parameter_acceptance(run),
    }


def _parameter_acceptance(run: dict[str, Any]) -> str:
    recommendation = build_backtest_recommendation_summary([run])
    status = recommendation.get("acceptance_status")
    return status if isinstance(status, str) else "not_evaluated"


def _sweep_warnings(runs: list[dict[str, Any]], *, accepted_count: int) -> list[str]:
    warnings: list[str] = []
    if accepted_count == 0:
        warnings.extend(["no_accepted_parameter_sets", "all_parameter_sets_rejected"])
    best = runs[0] if runs else {}
    if isinstance(best.get("score_warnings"), list) and best.get("score_warnings"):
        warnings.append("best_parameter_set_has_warnings")
    parameter_pairs = {
        (
            (run.get("summary") if isinstance(run.get("summary"), dict) else {}).get("entry_below"),
            (run.get("summary") if isinstance(run.get("summary"), dict) else {}).get("exit_above"),
        )
        for run in runs
        if isinstance(run, dict)
    }
    if len(parameter_pairs) <= 1 and len(runs) > 1:
        warnings.append("low_parameter_diversity")
    return sorted(set(warnings))


def _sweep_run_sort_key(run: dict[str, Any]) -> tuple[Any, ...]:
    summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    score = _decimal_sort_value(run.get("overall_score") or summary.get("overall_score"))
    return_pct = _decimal_sort_value(summary.get("total_return_pct"))
    drawdown = _decimal_sort_value(summary.get("max_drawdown_pct"))
    return (
        -score,
        -return_pct,
        drawdown,
        str(summary.get("entry_below")),
        str(summary.get("exit_above")),
        str(summary.get("order_quantity")),
        str(run.get("run_name")),
    )


def _decimal_sort_value(value: Any) -> Decimal:
    if value in (None, "", "Unavailable"):
        return Decimal("-Infinity")
    return Decimal(str(value))


def _available(value: Any) -> Any:
    return "Unavailable" if value in (None, "") else value


def _decimal_to_string(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _slug_decimal(value: Decimal) -> str:
    return _decimal_to_string(value).replace("-", "neg").replace(".", "p")


def _markdown_value(value: Any) -> Any:
    return "Unavailable" if value is None else value
