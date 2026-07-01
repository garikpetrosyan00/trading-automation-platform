import json
from io import StringIO

from app.cli import run_portfolio_backtest_comparison_smoke as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


def test_portfolio_backtest_comparison_smoke_writes_runs_and_comparison(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "runs" / "portfolio_smoke"
    stdout = StringIO()

    exit_code = cli.main(["--csv", str(csv_path), "--output-dir", str(output_dir)], stdout=stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"] == "PASS"
    assert payload["runs_count"] == 2
    assert "Local CSV artifact comparison only" in payload["safety_note"]
    assert [run["run_name"] for run in payload["runs"]] == [
        "base_price_threshold",
        "candidate_price_threshold",
    ]
    assert (output_dir / "base_price_threshold" / "summary.json").exists()
    assert (output_dir / "base_price_threshold" / "trades.csv").exists()
    assert (output_dir / "base_price_threshold" / "equity_curve.csv").exists()
    assert (output_dir / "candidate_price_threshold" / "summary.json").exists()
    assert (output_dir / "candidate_price_threshold" / "trades.csv").exists()
    assert (output_dir / "candidate_price_threshold" / "equity_curve.csv").exists()

    comparison = payload["comparison"]
    assert comparison["result"] == "PASS"
    assert comparison["runs_count"] == 2
    assert comparison["ranking_metrics"] == ["overall_score", "total_return", "ending_balance", "max_drawdown_pct"]
    assert "overall_score" in comparison["rankings"]
    assert all("overall_score" in run for run in comparison["runs"])
    assert comparison["recommendation"]["recommended_run"]["run_name"] in {
        "base_price_threshold",
        "candidate_price_threshold",
    }
    assert comparison["recommendation"]["recommendation_status"] in {
        "weak_recommendation",
        "not_recommended",
    }
    assert [item["run_name"] for item in comparison["rankings"]["total_return"]] == [
        "base_price_threshold",
        "candidate_price_threshold",
    ]
    assert [item["run_name"] for item in comparison["rankings"]["ending_balance"]] == [
        "base_price_threshold",
        "candidate_price_threshold",
    ]
    assert all(item["available"] is True for item in comparison["rankings"]["max_drawdown_pct"])


def test_portfolio_backtest_comparison_smoke_output_includes_summary_metrics(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "runs" / "portfolio_smoke"
    stdout = StringIO()

    assert cli.main(["--csv", str(csv_path), "--output-dir", str(output_dir)], stdout=stdout) == 0

    payload = json.loads(stdout.getvalue())
    base_summary = payload["runs"][0]["summary"]
    assert base_summary["strategy_type"] == "price_threshold"
    assert base_summary["entry_below"] == "95000"
    assert base_summary["exit_above"] == "105000"
    assert base_summary["starting_balance"] == "10000"
    assert base_summary["ending_balance"] == "10113.005"
    assert base_summary["total_return"] == "113.005"
    assert base_summary["realized_pnl"] == "113.005"
    assert base_summary["trades_count"] == 2
    assert base_summary["completed_round_trips"] == 1
    assert base_summary["win_count"] == 1
    assert base_summary["loss_count"] == 0
    assert base_summary["breakeven_count"] == 0
    assert base_summary["win_rate_pct"] == "100"
    assert base_summary["average_winning_trade_pnl"] == "113.005"
    assert base_summary["average_losing_trade_pnl"] is None
    assert base_summary["average_trade_pnl"] == "113.005"
    assert base_summary["best_trade_pnl"] == "113.005"
    assert base_summary["worst_trade_pnl"] == "113.005"
    assert base_summary["profit_factor"] is None
    assert "max_drawdown_amount" in base_summary
    assert "max_drawdown_pct" in base_summary
    assert base_summary["exposure_pct"] == "50"
    scored_base = next(run for run in payload["comparison"]["runs"] if run["run_name"] == "base_price_threshold")
    assert scored_base["summary"]["overall_score"] == scored_base["overall_score"]
    assert scored_base["score_components"]["final_normalized_score"] == scored_base["overall_score"]


def test_portfolio_backtest_comparison_smoke_refuses_non_empty_output_without_overwrite(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "runs" / "portfolio_smoke"
    output_dir.mkdir(parents=True)
    (output_dir / "old.txt").write_text("old\n", encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.main(["--csv", str(csv_path), "--output-dir", str(output_dir)], stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output directory is not empty; pass --overwrite to replace: {output_dir}",
        "result": "FAIL",
    }
    assert (output_dir / "old.txt").exists()


def test_portfolio_backtest_comparison_smoke_overwrite_rebuilds_output(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "runs" / "portfolio_smoke"
    output_dir.mkdir(parents=True)
    (output_dir / "old.txt").write_text("old\n", encoding="utf-8")

    exit_code = cli.main(
        ["--csv", str(csv_path), "--output-dir", str(output_dir), "--overwrite"],
        stdout=StringIO(),
    )

    assert exit_code == 0
    assert not (output_dir / "old.txt").exists()
    assert (output_dir / "base_price_threshold" / "summary.json").exists()


def test_portfolio_backtest_comparison_smoke_generated_artifacts_are_local_only(tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)
    output_dir = tmp_path / "data" / "backtests" / "runs" / "portfolio_smoke"

    assert cli.main(["--csv", str(csv_path), "--output-dir", str(output_dir)], stdout=StringIO()) == 0

    generated_files = sorted(path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*") if path.is_file())
    assert generated_files == [
        "base_price_threshold/equity_curve.csv",
        "base_price_threshold/summary.json",
        "base_price_threshold/trades.csv",
        "candidate_price_threshold/equity_curve.csv",
        "candidate_price_threshold/summary.json",
        "candidate_price_threshold/trades.csv",
    ]


def test_portfolio_backtest_comparison_smoke_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    csv_path = write_demo_csv(tmp_path)

    assert cli.main(["--csv", str(csv_path), "--output-dir", str(tmp_path / "portfolio_smoke")], stdout=StringIO()) == 0

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
