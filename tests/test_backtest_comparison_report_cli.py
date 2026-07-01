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
    stdout_payload = json.loads(stdout.getvalue())
    assert stdout_payload["output_json"] == str(output_json)
    assert stdout_payload["output_md"] is None
    assert stdout_payload["result"] == "PASS"
    assert stdout_payload["run_count"] == 2
    assert stdout_payload["export_manifest"]["comparison_row_count"] == 2
    assert stdout_payload["export_manifest"]["validation_status"] == "passed"
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["result"] == "PASS"
    assert report["generated_at"] == GENERATED_AT
    assert report["run_count"] == 2
    assert report["ranking_metrics"] == ["overall_score", "total_return", "ending_balance", "max_drawdown_pct"]
    assert "Local backtest artifact comparison report only" in report["safety_note"]
    assert [run["run_path"] for run in report["runs"]] == ["candidate", "base"]
    candidate = report["runs"][0]
    assert candidate["summary"]["strategy_type"] == "moving_average_crossover"
    assert candidate["summary"]["fast_window"] == "2"
    assert candidate["summary"]["average_winning_trade_pnl"] == "100"
    assert candidate["summary"]["average_losing_trade_pnl"] is None
    assert candidate["summary"]["average_trade_pnl"] == "100"
    assert candidate["summary"]["best_trade_pnl"] == "100"
    assert candidate["summary"]["worst_trade_pnl"] == "100"
    assert candidate["summary"]["profit_factor"] is None
    assert candidate["summary"]["max_drawdown_amount"] == "50"
    assert candidate["summary"]["exposure_pct"] == "50"
    assert candidate["overall_score"] == candidate["summary"]["overall_score"]
    assert candidate["score_components"]["final_normalized_score"] == candidate["overall_score"]
    assert "infinite_or_unavailable_profit_factor" in candidate["score_warnings"]
    assert report["recommendation"]["recommended_run"]["run_name"] == "candidate"
    assert report["recommendation"]["recommended_run"]["run_path"] == "candidate"
    assert report["recommendation"]["recommendation_status"] == "weak_recommendation"
    assert report["recommendation"]["acceptance_status"] == "rejected"
    assert "too_few_trades" in report["recommendation"]["acceptance_failures"]
    assert "best_run_has_too_few_trades" in report["recommendation"]["recommendation_warnings"]
    assert report["executive_summary"]["decision"] == "reject_candidate"
    assert report["executive_summary"]["best_run_label"] == "candidate"
    assert report["executive_summary"]["acceptance_status"] == "rejected"
    assert report["executive_summary"]["recommendation_status"] == "weak_recommendation"
    assert "too_few_trades" in report["executive_summary"]["key_risks"]
    manifest = report["export_manifest"]
    assert manifest["schema_version"] == "1"
    assert manifest["artifact_type"] == "backtest_comparison_report"
    assert manifest["generated_by"] == "export_backtest_comparison_report"
    assert manifest["comparison_row_count"] == 2
    assert manifest["has_recommendation"] is True
    assert manifest["has_acceptance_gates"] is True
    assert manifest["has_executive_summary"] is True
    assert manifest["validation_status"] == "passed"
    assert manifest["validation_warnings"] == []
    assert manifest["validation_errors"] == []
    assert manifest["output_artifacts"] == {"json_report_path": "reports/comparison_report.json"}
    assert manifest["input_artifacts"][0] == {
        "label": "candidate",
        "run_id": "candidate",
        "summary_path": "candidate/summary.json",
        "trades_path": "candidate/trades.csv",
        "equity_curve_path": "candidate/equity_curve.csv",
        "strategy": "moving_average_crossover",
        "artifact_exists": True,
    }
    assert str(tmp_path.resolve()) not in json.dumps(manifest, sort_keys=True)
    assert [item["run_name"] for item in report["rankings"]["overall_score"]] == ["candidate", "base"]
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
    assert "## Executive Summary" in markdown
    assert "| Decision | reject_candidate |" in markdown
    assert "| candidate | candidate |" in markdown
    assert "Overall Score" in markdown
    assert "Score Warnings" in markdown
    assert "## Recommendation" in markdown
    assert "Status: `weak_recommendation`" in markdown
    assert "Acceptance status: `rejected`" in markdown
    assert "Acceptance Failures" in markdown
    assert "Acceptance Warnings" in markdown
    assert "Recommendation Warnings" in markdown
    assert "## Export Manifest" in markdown
    assert "| Validation Status | passed |" in markdown
    assert "### `overall_score`" in markdown
    assert "### `total_return`" in markdown
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["export_manifest"]["output_artifacts"] == {
        "json_report_path": "comparison_report.json",
        "markdown_report_path": "comparison_report.md",
    }


def test_export_backtest_comparison_report_reads_existing_comparison_json(tmp_path) -> None:
    comparison_json = tmp_path / "comparison.json"
    comparison_json.write_text(
        json.dumps(
            {
                "result": "PASS",
                "runs_count": 2,
                "ranking_metrics": ["overall_score", "total_return", "ending_balance", "max_drawdown_pct"],
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
                    "overall_score": [
                        {
                            "rank": 1,
                            "run_name": "candidate",
                            "run_dir": str(tmp_path / "runs" / "candidate"),
                            "metric": "overall_score",
                            "value": "55",
                            "available": True,
                        }
                    ],
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
    assert report["recommendation"]["recommended_run"]["run_path"] == "candidate"
    assert "acceptance_status" in report["recommendation"]
    assert report["executive_summary"]["decision"] == "reject_candidate"
    assert report["export_manifest"]["output_artifacts"] == {"json_report_path": "report.json"}


def test_export_backtest_comparison_report_tolerates_older_comparison_without_scores_or_recommendation(tmp_path) -> None:
    comparison_json = tmp_path / "comparison.json"
    comparison_json.write_text(
        json.dumps(
            {
                "result": "PASS",
                "runs_count": 2,
                "ranking_metrics": ["total_return"],
                "runs": [
                    {"run_name": "base", "run_dir": str(tmp_path / "runs" / "base"), "summary": {"total_return": "10"}},
                    {"run_name": "candidate", "run_dir": str(tmp_path / "runs" / "candidate"), "summary": {"total_return": "20"}},
                ],
                "rankings": {"total_return": []},
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
    assert report["recommendation"]["recommendation_status"] == "no_valid_runs"
    assert report["recommendation"]["recommended_run"] is None
    assert report["recommendation"]["acceptance_status"] == "not_evaluated"
    assert report["executive_summary"]["decision"] == "no_decision"
    assert report["export_manifest"]["comparison_row_count"] == 2


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
