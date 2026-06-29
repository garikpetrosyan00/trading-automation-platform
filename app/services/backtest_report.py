import csv
import json
from pathlib import Path
from typing import Any


class BacktestReportError(ValueError):
    pass


RUN_FIELDS = (
    ("symbol", "Symbol"),
    ("timeframe", "Timeframe"),
    ("started_at", "Started At"),
    ("ended_at", "Ended At"),
    ("candles_count", "Candles"),
)

CONFIG_FIELDS = (
    ("strategy_type", "Strategy Type"),
    ("prepared_csv", "Prepared CSV"),
    ("initial_balance", "Initial Balance"),
    ("fee_rate", "Fee Rate"),
    ("entry_below", "Entry Below"),
    ("exit_above", "Exit Above"),
    ("order_quantity", "Order Quantity"),
)

METRIC_FIELDS = (
    ("final_balance", "Final Balance"),
    ("final_position_quantity", "Final Position Quantity"),
    ("final_equity", "Final Equity"),
    ("total_return_pct", "Total Return %"),
    ("realized_pnl", "Realized PnL"),
    ("unrealized_pnl", "Unrealized PnL"),
    ("trades_count", "Trades"),
    ("buy_count", "Buys"),
    ("sell_count", "Sells"),
    ("win_rate_pct", "Win Rate %"),
    ("fees_paid", "Fees Paid"),
    ("max_drawdown_pct", "Max Drawdown %"),
    ("buy_and_hold_return_pct", "Buy And Hold Return %"),
)


def build_backtest_markdown_report(
    *,
    run_dir: str | Path,
    title: str | None = None,
    comparison_json: str | Path | None = None,
) -> str:
    run_path = Path(run_dir)
    summary = _load_summary(run_path)
    comparison = _load_comparison(Path(comparison_json)) if comparison_json is not None else None
    report_title = title or "Backtest Report"

    lines = [
        f"# {_markdown_text(report_title)}",
        "",
        "Safety note: local CSV simulation only. This is not live or testnet execution and does not place orders.",
        "",
        "## Run",
        "",
        _table(["Field", "Value"], [(label, _value(summary.get(key))) for key, label in RUN_FIELDS]),
        "",
        "## Strategy / Config",
        "",
        _table(["Field", "Value"], [(label, _value(summary.get(key))) for key, label in CONFIG_FIELDS]),
        "",
        "## Key Performance Metrics",
        "",
        _table(["Metric", "Value"], [(label, _value(summary.get(key))) for key, label in METRIC_FIELDS]),
        "",
        "## Artifacts",
        "",
        _table(
            ["Artifact", "Rows / Status"],
            [
                ("summary.json", "Available"),
                ("trades.csv", _artifact_rows(run_path / "trades.csv")),
                ("equity_curve.csv", _artifact_rows(run_path / "equity_curve.csv")),
            ],
        ),
    ]
    if comparison is not None:
        lines.extend(["", "## Comparison", "", _comparison_section(comparison)])
    return "\n".join(lines) + "\n"


def _load_summary(run_dir: Path) -> dict[str, Any]:
    if not run_dir.exists():
        raise BacktestReportError(f"run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise BacktestReportError(f"run path is not a directory: {run_dir}")
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise BacktestReportError(f"summary.json does not exist: {summary_path}")
    if not summary_path.is_file():
        raise BacktestReportError(f"summary.json path is not a file: {summary_path}")
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BacktestReportError(f"summary.json is not valid JSON: {summary_path}") from exc
    if not isinstance(payload, dict):
        raise BacktestReportError(f"summary.json must contain a JSON object: {summary_path}")
    return payload


def _load_comparison(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise BacktestReportError(f"comparison JSON does not exist: {path}")
    if not path.is_file():
        raise BacktestReportError(f"comparison JSON path is not a file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BacktestReportError(f"comparison JSON is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise BacktestReportError(f"comparison JSON must contain a JSON object: {path}")
    return payload


def _comparison_section(comparison: dict[str, Any]) -> str:
    metrics = comparison.get("metrics")
    if isinstance(metrics, dict):
        rows = []
        for metric in sorted(metrics):
            details = metrics[metric]
            if isinstance(details, dict):
                rows.append(
                    (
                        metric,
                        _value(details.get("base")),
                        _value(details.get("candidate")),
                        _value(details.get("delta")),
                        "Available" if details.get("available") is True else _value(details.get("reason")),
                    )
                )
            else:
                rows.append((metric, "Unavailable", "Unavailable", "Unavailable", "Unavailable"))
        return _table(["Metric", "Base", "Candidate", "Delta", "Status"], rows)

    deltas = comparison.get("deltas")
    if isinstance(deltas, dict):
        rows = [(metric, _value(deltas.get(metric))) for metric in sorted(deltas)]
        return _table(["Metric", "Delta"], rows)

    return "Unavailable"


def _artifact_rows(path: Path) -> str:
    if not path.is_file():
        return "Unavailable"
    with path.open(newline="", encoding="utf-8") as handle:
        return str(sum(1 for _row in csv.DictReader(handle)))


def _table(headers: list[str], rows: list[tuple[Any, ...]]) -> str:
    rendered = [
        "| " + " | ".join(_markdown_text(header) for header in headers) + " |",
        "| " + " | ".join("---" for _header in headers) + " |",
    ]
    for row in rows:
        rendered.append("| " + " | ".join(_markdown_text(cell) for cell in row) + " |")
    return "\n".join(rendered)


def _value(value: Any) -> str:
    if value in (None, ""):
        return "Unavailable"
    return str(value)


def _markdown_text(value: Any) -> str:
    return _value(value).replace("|", "\\|").replace("\n", " ")
