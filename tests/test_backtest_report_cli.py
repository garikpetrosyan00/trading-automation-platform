import csv
import json
from io import StringIO

from app.cli import export_backtest_report as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


def test_export_backtest_report_writes_markdown(tmp_path) -> None:
    run_dir = write_run_dir(
        tmp_path,
        "run",
        {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "prepared_csv": "data/backtests/datasets/BTCUSDT_1h_prepared.csv",
            "initial_balance": "10000",
            "final_equity": "10125.25",
            "total_return_pct": "1.2525",
            "trades_count": 2,
            "win_rate_pct": "100",
            "max_drawdown_pct": "0.5",
        },
    )
    output_md = tmp_path / "reports" / "run.md"
    stdout = StringIO()

    exit_code = cli.main(["--run-dir", str(run_dir), "--output-md", str(output_md)], stdout=stdout)

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {
        "comparison_json": None,
        "output_md": str(output_md),
        "result": "PASS",
        "run_dir": str(run_dir),
    }
    markdown = output_md.read_text(encoding="utf-8")
    assert "# Backtest Report" in markdown
    assert "| Symbol | BTCUSDT |" in markdown
    assert "| Timeframe | 1h |" in markdown
    assert "| Prepared CSV | data/backtests/datasets/BTCUSDT_1h_prepared.csv |" in markdown
    assert "| Final Equity | 10125.25 |" in markdown
    assert "| trades.csv | 2 |" in markdown
    assert "| equity_curve.csv | 3 |" in markdown
    assert "local CSV simulation only" in markdown


def test_export_backtest_report_missing_run_directory_fails_cleanly(tmp_path) -> None:
    missing_dir = tmp_path / "missing"
    stdout = StringIO()

    exit_code = cli.main(
        ["--run-dir", str(missing_dir), "--output-md", str(tmp_path / "report.md")],
        stdout=stdout,
    )

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"run directory does not exist: {missing_dir}",
        "result": "FAIL",
    }


def test_export_backtest_report_missing_summary_fails_cleanly(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stdout = StringIO()

    exit_code = cli.main(
        ["--run-dir", str(run_dir), "--output-md", str(tmp_path / "report.md")],
        stdout=stdout,
    )

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"summary.json does not exist: {run_dir / 'summary.json'}",
        "result": "FAIL",
    }


def test_export_backtest_report_marks_missing_optional_metrics_unavailable(tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run", {"symbol": "ETHUSDT", "final_equity": "10000"})
    output_md = tmp_path / "report.md"

    assert cli.main(["--run-dir", str(run_dir), "--output-md", str(output_md)], stdout=StringIO()) == 0

    markdown = output_md.read_text(encoding="utf-8")
    assert "| Symbol | ETHUSDT |" in markdown
    assert "| Timeframe | Unavailable |" in markdown
    assert "| Strategy Type | Unavailable |" in markdown
    assert "| Win Rate % | Unavailable |" in markdown


def test_export_backtest_report_includes_comparison_json(tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run", {"symbol": "BTCUSDT", "final_equity": "10100"})
    comparison_json = tmp_path / "comparison.json"
    comparison_json.write_text(
        json.dumps(
            {
                "result": "PASS",
                "metrics": {
                    "final_equity": {
                        "available": True,
                        "base": "10000",
                        "candidate": "10100",
                        "delta": "100",
                    },
                    "win_rate_pct": {
                        "available": False,
                        "base": None,
                        "candidate": None,
                        "delta": None,
                        "reason": "metric missing or null",
                    },
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    output_md = tmp_path / "report.md"

    exit_code = cli.main(
        [
            "--run-dir",
            str(run_dir),
            "--comparison-json",
            str(comparison_json),
            "--output-md",
            str(output_md),
        ],
        stdout=StringIO(),
    )

    assert exit_code == 0
    markdown = output_md.read_text(encoding="utf-8")
    assert "## Comparison" in markdown
    assert "| final_equity | 10000 | 10100 | 100 | Available |" in markdown
    assert "| win_rate_pct | Unavailable | Unavailable | Unavailable | metric missing or null |" in markdown


def test_export_backtest_report_uses_custom_title(tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run", {"symbol": "BTCUSDT"})
    output_md = tmp_path / "report.md"

    assert (
        cli.main(
            ["--run-dir", str(run_dir), "--output-md", str(output_md), "--title", "BTCUSDT Smoke Report"],
            stdout=StringIO(),
        )
        == 0
    )

    assert output_md.read_text(encoding="utf-8").startswith("# BTCUSDT Smoke Report\n")


def test_export_backtest_report_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run", {"symbol": "BTCUSDT", "final_equity": "10000"})

    assert cli.main(["--run-dir", str(run_dir), "--output-md", str(tmp_path / "report.md")], stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def write_run_dir(tmp_path, name: str, summary: dict):
    run_dir = tmp_path / name
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(run_dir / "trades.csv", ["timestamp", "side"], [["2025-01-01T00:00:00Z", "buy"], ["2025-01-01T01:00:00Z", "sell"]])
    write_csv(
        run_dir / "equity_curve.csv",
        ["timestamp", "equity"],
        [
            ["2025-01-01T00:00:00Z", "10000"],
            ["2025-01-01T01:00:00Z", "10050"],
            ["2025-01-01T02:00:00Z", "10100"],
        ],
    )
    return run_dir


def write_csv(path, fieldnames: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)
