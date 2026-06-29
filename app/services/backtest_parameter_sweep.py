import csv
import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.cli.run_backtest import _summary_payload, _to_jsonable, _write_output_dir
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
        "| Rank | Run | Entry Below | Exit Above | Final Equity | Total Return % |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"{rows}\n"
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
