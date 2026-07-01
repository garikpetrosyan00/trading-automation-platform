import json
from io import StringIO

from app.cli import run_portfolio_backtest_report_demo as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


GENERATED_AT = "2026-07-01T00:00:00Z"


def test_portfolio_backtest_report_demo_runs_e2e_and_validates_report(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "portfolio_report_demo"
    stdout = StringIO()

    exit_code = cli.main(
        [
            "--csv",
            str(csv_path),
            "--output-dir",
            str(output_dir),
            "--generated-at",
            GENERATED_AT,
        ],
        stdout=stdout,
    )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"] == "PASS"
    assert payload["output_dir"] == str(output_dir)
    assert payload["run_count"] == 2
    assert "Local backtest artifact comparison report only" in payload["safety_note"]
    assert payload["validation"]["valid"] is True
    assert payload["validation"]["errors"] == []

    artifacts = payload["artifacts"]
    assert artifacts["report_json"] == str(output_dir / "comparison_report.json")
    assert artifacts["comparison_json"] == str(output_dir / "comparison.json")
    assert artifacts["report_md"] is None
    assert (output_dir / "base_price_threshold" / "summary.json").exists()
    assert (output_dir / "base_price_threshold" / "trades.csv").exists()
    assert (output_dir / "base_price_threshold" / "equity_curve.csv").exists()
    assert (output_dir / "candidate_price_threshold" / "summary.json").exists()
    assert (output_dir / "candidate_price_threshold" / "trades.csv").exists()
    assert (output_dir / "candidate_price_threshold" / "equity_curve.csv").exists()
    assert (output_dir / "comparison.json").exists()
    assert (output_dir / "comparison_report.json").exists()

    report = json.loads((output_dir / "comparison_report.json").read_text(encoding="utf-8"))
    assert report["generated_at"] == GENERATED_AT
    assert report["run_count"] == 2
    assert report["recommendation"]["recommended_run"]["run_name"] in {
        "base_price_threshold",
        "candidate_price_threshold",
    }
    assert report["recommendation"]["recommendation_status"] in {
        "weak_recommendation",
        "not_recommended",
    }
    assert report["recommendation"]["acceptance_status"] in {
        "rejected",
        "accepted_with_warnings",
    }
    assert report["executive_summary"]["decision"] in {
        "reject_candidate",
        "accept_with_warnings",
    }
    assert "summary_text" in report["executive_summary"]
    assert report["export_manifest"]["comparison_row_count"] == 2
    assert report["export_manifest"]["has_recommendation"] is True
    assert report["export_manifest"]["has_acceptance_gates"] is True
    assert report["export_manifest"]["has_executive_summary"] is True
    assert report["export_manifest"]["validation_status"] == "passed"
    assert report["export_manifest"]["output_artifacts"] == {"json_report_path": "comparison_report.json"}
    assert str(tmp_path.resolve()) not in json.dumps(report["export_manifest"], sort_keys=True)
    assert [run["run_path"] for run in report["runs"]] == [
        "base_price_threshold",
        "candidate_price_threshold",
    ]
    assert [item["run_name"] for item in payload["rankings"]["total_return"]] == [
        "base_price_threshold",
        "candidate_price_threshold",
    ]
    assert [item["run_name"] for item in payload["rankings"]["ending_balance"]] == [
        "base_price_threshold",
        "candidate_price_threshold",
    ]
    assert "max_drawdown_pct" in payload["rankings"]
    assert payload["diagnostics"]["base_price_threshold"]["completed_round_trips"] == 1
    assert payload["diagnostics"]["base_price_threshold"]["average_winning_trade_pnl"] == "113.005"
    assert payload["diagnostics"]["base_price_threshold"]["average_losing_trade_pnl"] is None
    assert payload["diagnostics"]["base_price_threshold"]["profit_factor"] is None
    assert payload["diagnostics"]["base_price_threshold"]["max_drawdown_amount"] == "0.94"
    assert payload["diagnostics"]["base_price_threshold"]["exposure_pct"] == "50"


def test_portfolio_backtest_report_demo_writes_optional_markdown_report(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "portfolio_report_demo"
    output_md = tmp_path / "reports" / "portfolio_report.md"
    stdout = StringIO()

    exit_code = cli.main(
        [
            "--csv",
            str(csv_path),
            "--output-dir",
            str(output_dir),
            "--output-md",
            str(output_md),
            "--generated-at",
            GENERATED_AT,
        ],
        stdout=stdout,
    )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["artifacts"]["report_md"] == str(output_md)
    markdown = output_md.read_text(encoding="utf-8")
    assert "# Backtest Comparison Report" in markdown
    assert "Generated at: `2026-07-01T00:00:00Z`" in markdown
    assert "Local backtest artifact comparison report only" in markdown
    assert "## Executive Summary" in markdown
    assert "## Recommendation" in markdown
    assert "Acceptance status:" in markdown
    assert "## Export Manifest" in markdown
    assert "### `total_return`" in markdown


def test_portfolio_backtest_report_demo_refuses_non_empty_output_without_overwrite(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "portfolio_report_demo"
    output_dir.mkdir()
    old_file = output_dir / "old.txt"
    old_file.write_text("old\n", encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.main(["--csv", str(csv_path), "--output-dir", str(output_dir)], stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output directory is not empty; pass --overwrite to replace: {output_dir}",
        "result": "FAIL",
    }
    assert old_file.read_text(encoding="utf-8") == "old\n"


def test_portfolio_backtest_report_demo_overwrite_rebuilds_output(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "portfolio_report_demo"
    output_dir.mkdir()
    old_file = output_dir / "old.txt"
    old_file.write_text("old\n", encoding="utf-8")

    exit_code = cli.main(
        ["--csv", str(csv_path), "--output-dir", str(output_dir), "--overwrite"],
        stdout=StringIO(),
    )

    assert exit_code == 0
    assert not old_file.exists()
    assert (output_dir / "comparison_report.json").exists()


def test_portfolio_backtest_report_demo_refuses_existing_markdown_without_overwrite(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "portfolio_report_demo"
    output_md = tmp_path / "portfolio_report.md"
    output_md.write_text("old\n", encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.main(
        [
            "--csv",
            str(csv_path),
            "--output-dir",
            str(output_dir),
            "--output-md",
            str(output_md),
        ],
        stdout=stdout,
    )

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output file already exists; pass --overwrite to replace: {output_md}",
        "result": "FAIL",
    }
    assert output_md.read_text(encoding="utf-8") == "old\n"


def test_portfolio_backtest_report_demo_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)

    assert (
        cli.main(
            ["--csv", str(csv_path), "--output-dir", str(tmp_path / "portfolio_report_demo")],
            stdout=StringIO(),
        )
        == 0
    )

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def write_demo_csv(tmp_path):
    path = tmp_path / "BTCUSDT_1h_demo.csv"
    path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2025-01-01T00:00:00Z,96000,97000,94000,95500,1",
                "2025-01-01T01:00:00Z,95500,95600,93000,94000,1",
                "2025-01-01T02:00:00Z,94000,100000,93500,99000,1",
                "2025-01-01T03:00:00Z,99000,106000,98500,105500,1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path
