import csv
import json
from io import StringIO

from app.cli import export_backtest_comparison_report as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


GENERATED_AT = "2026-07-01T00:00:00Z"


def test_export_backtest_comparison_report_writes_json_from_run_dirs(tmp_path) -> None:
    base_dir = write_run_dir(
        tmp_path,
        "base",
        {
            "strategy_type": "price_threshold",
            "entry_below": "95",
            "exit_above": "105",
            "starting_balance": "10000",
            "ending_balance": "10050",
            "total_return": "50",
            "average_winning_trade_pnl": "50",
            "average_losing_trade_pnl": None,
            "average_trade_pnl": "50",
            "best_trade_pnl": "50",
            "worst_trade_pnl": "50",
            "profit_factor": None,
            "breakeven_count": 0,
            "max_drawdown_amount": "125",
            "max_drawdown_pct": "1.25",
            "exposure_pct": "50",
        },
    )
    candidate_dir = write_run_dir(
        tmp_path,
        "candidate",
        {
            "strategy_type": "moving_average_crossover",
            "fast_window": "2",
            "slow_window": "3",
            "starting_balance": "10000",
            "ending_balance": "10100",
            "total_return": "100",
            "average_winning_trade_pnl": "100",
            "average_losing_trade_pnl": None,
            "average_trade_pnl": "100",
            "best_trade_pnl": "100",
            "worst_trade_pnl": "100",
            "profit_factor": None,
            "breakeven_count": 0,
            "max_drawdown_amount": "50",
            "max_drawdown_pct": "0.5",
            "exposure_pct": "50",
        },
    )
    output_json = tmp_path / "reports" / "comparison_report.json"
    stdout = StringIO()

    exit_code = cli.main(
        [
            "--run-dir",
            str(base_dir),
            "--run-dir",
            str(candidate_dir),
            "--output-json",
            str(output_json),
            "--generated-at",
            GENERATED_AT,
        ],
        stdout=stdout,
    )

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {
        "output_json": str(output_json),
        "output_md": None,
        "result": "PASS",
        "run_count": 2,
    }
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["result"] == "PASS"
    assert report["generated_at"] == GENERATED_AT
    assert report["run_count"] == 2
    assert report["ranking_metrics"] == ["total_return", "ending_balance", "max_drawdown_pct"]
    assert "Local backtest artifact comparison report only" in report["safety_note"]
    assert [run["run_path"] for run in report["runs"]] == ["base", "candidate"]
    assert report["runs"][1]["summary"]["strategy_type"] == "moving_average_crossover"
    assert report["runs"][1]["summary"]["fast_window"] == "2"
    assert report["runs"][1]["summary"]["average_winning_trade_pnl"] == "100"
    assert report["runs"][1]["summary"]["average_losing_trade_pnl"] is None
    assert report["runs"][1]["summary"]["average_trade_pnl"] == "100"
    assert report["runs"][1]["summary"]["best_trade_pnl"] == "100"
    assert report["runs"][1]["summary"]["worst_trade_pnl"] == "100"
    assert report["runs"][1]["summary"]["profit_factor"] is None
    assert report["runs"][1]["summary"]["max_drawdown_amount"] == "50"
    assert report["runs"][1]["summary"]["exposure_pct"] == "50"
    assert [item["run_name"] for item in report["rankings"]["total_return"]] == ["candidate", "base"]
    assert [item["run_path"] for item in report["rankings"]["ending_balance"]] == ["candidate", "base"]
    assert [item["run_name"] for item in report["rankings"]["max_drawdown_pct"]] == ["candidate", "base"]


def test_export_backtest_comparison_report_writes_markdown(tmp_path) -> None:
    base_dir = write_run_dir(tmp_path, "base", {"starting_balance": "10000", "ending_balance": "10050", "total_return": "50"})
    candidate_dir = write_run_dir(
        tmp_path,
        "candidate",
        {"starting_balance": "10000", "ending_balance": "10100", "total_return": "100"},
    )
    output_json = tmp_path / "comparison_report.json"
    output_md = tmp_path / "comparison_report.md"

    exit_code = cli.main(
        [
            "--run-dir",
            str(base_dir),
            "--run-dir",
            str(candidate_dir),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
            "--generated-at",
            GENERATED_AT,
        ],
        stdout=StringIO(),
    )

    assert exit_code == 0
    markdown = output_md.read_text(encoding="utf-8")
    assert "# Backtest Comparison Report" in markdown
    assert "Generated at: `2026-07-01T00:00:00Z`" in markdown
    assert "Local backtest artifact comparison report only" in markdown
    assert "| candidate | candidate |" in markdown
    assert "### `total_return`" in markdown


def test_export_backtest_comparison_report_reads_existing_comparison_json(tmp_path) -> None:
    comparison_json = tmp_path / "comparison.json"
    comparison_json.write_text(
        json.dumps(
            {
                "result": "PASS",
                "runs_count": 2,
                "ranking_metrics": ["total_return", "ending_balance", "max_drawdown_pct"],
                "runs": [
                    {
                        "run_name": "base",
                        "run_dir": str(tmp_path / "runs" / "base"),
                        "summary": {"run_name": "base", "strategy_type": "price_threshold", "total_return": "10"},
                        "artifacts": {"summary_json": True},
                    },
                    {
                        "run_name": "candidate",
                        "run_dir": str(tmp_path / "runs" / "candidate"),
                        "summary": {"run_name": "candidate", "strategy_type": "price_threshold", "total_return": "20"},
                        "artifacts": {"summary_json": True},
                    },
                ],
                "rankings": {
                    "total_return": [
                        {
                            "rank": 1,
                            "run_name": "candidate",
                            "run_dir": str(tmp_path / "runs" / "candidate"),
                            "metric": "total_return",
                            "value": "20",
                            "available": True,
                        }
                    ],
                    "ending_balance": [],
                    "max_drawdown_pct": [],
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    output_json = tmp_path / "report.json"

    exit_code = cli.main(
        [
            "--comparison-json",
            str(comparison_json),
            "--artifact-root",
            str(tmp_path / "runs"),
            "--output-json",
            str(output_json),
            "--generated-at",
            GENERATED_AT,
        ],
        stdout=StringIO(),
    )

    assert exit_code == 0
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert [run["run_path"] for run in report["runs"]] == ["base", "candidate"]
    assert report["rankings"]["total_return"][0]["run_path"] == "candidate"


def test_export_backtest_comparison_report_refuses_existing_output_without_overwrite(tmp_path) -> None:
    base_dir = write_run_dir(tmp_path, "base", {"final_equity": "10000"})
    candidate_dir = write_run_dir(tmp_path, "candidate", {"final_equity": "10010"})
    output_json = tmp_path / "report.json"
    output_json.write_text("old\n", encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.main(
        [
            "--run-dir",
            str(base_dir),
            "--run-dir",
            str(candidate_dir),
            "--output-json",
            str(output_json),
        ],
        stdout=stdout,
    )

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output file already exists; pass --overwrite to replace: {output_json}",
        "result": "FAIL",
    }
    assert output_json.read_text(encoding="utf-8") == "old\n"


def test_export_backtest_comparison_report_overwrite_replaces_existing_output(tmp_path) -> None:
    base_dir = write_run_dir(tmp_path, "base", {"final_equity": "10000"})
    candidate_dir = write_run_dir(tmp_path, "candidate", {"final_equity": "10010"})
    output_json = tmp_path / "report.json"
    output_json.write_text("old\n", encoding="utf-8")

    exit_code = cli.main(
        [
            "--run-dir",
            str(base_dir),
            "--run-dir",
            str(candidate_dir),
            "--output-json",
            str(output_json),
            "--overwrite",
            "--generated-at",
            GENERATED_AT,
        ],
        stdout=StringIO(),
    )

    assert exit_code == 0
    assert json.loads(output_json.read_text(encoding="utf-8"))["result"] == "PASS"


def test_export_backtest_comparison_report_requires_two_run_dirs(tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "only", {"final_equity": "10000"})
    stderr = StringIO()

    exit_code = cli.main(
        ["--run-dir", str(run_dir), "--output-json", str(tmp_path / "report.json")],
        stderr=stderr,
    )

    assert exit_code == 2
    assert "--run-dir must be passed at least twice" in stderr.getvalue()


def test_export_backtest_comparison_report_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    base_dir = write_run_dir(tmp_path, "base", {"final_equity": "10000"})
    candidate_dir = write_run_dir(tmp_path, "candidate", {"final_equity": "10010"})

    assert (
        cli.main(
            [
                "--run-dir",
                str(base_dir),
                "--run-dir",
                str(candidate_dir),
                "--output-json",
                str(tmp_path / "report.json"),
            ],
            stdout=StringIO(),
        )
        == 0
    )

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
        [["2025-01-01T00:00:00Z", "10000"], ["2025-01-01T01:00:00Z", "10010"]],
    )
    return run_dir


def write_csv(path, fieldnames: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)
