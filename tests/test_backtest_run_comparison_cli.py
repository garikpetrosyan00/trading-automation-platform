import csv
import json
from io import StringIO

from app.cli import compare_backtest_runs as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


def test_compare_backtest_runs_reports_metric_deltas(tmp_path) -> None:
    base_dir = write_run_dir(
        tmp_path,
        "base",
        {
            "initial_balance": "10000",
            "final_equity": "10000",
            "final_balance": "9990",
            "total_return_pct": "0",
            "trades_count": 2,
            "win_rate_pct": "50",
            "max_drawdown_pct": "2.5",
            "fees_paid": "1.5",
        },
    )
    candidate_dir = write_run_dir(
        tmp_path,
        "candidate",
        {
            "initial_balance": "10000",
            "final_equity": "10125.25",
            "final_balance": "10125.25",
            "total_return_pct": "1.2525",
            "trades_count": 4,
            "win_rate_pct": "75",
            "max_drawdown_pct": "1.25",
            "fees_paid": "2",
        },
    )
    stdout = StringIO()

    exit_code = cli.main(
        ["--base-run-dir", str(base_dir), "--candidate-run-dir", str(candidate_dir)],
        stdout=stdout,
    )

    assert exit_code == 0
    report = json.loads(stdout.getvalue())
    assert report["result"] == "PASS"
    assert report["metrics"]["final_equity"] == {
        "available": True,
        "base": "10000",
        "candidate": "10125.25",
        "delta": "125.25",
    }
    assert report["metrics"]["ending_balance"]["delta"] == "125.25"
    assert report["metrics"]["total_return"]["delta"] == "125.25"
    assert report["metrics"]["trades_count"]["delta"] == "2"
    assert report["metrics"]["max_drawdown_pct"]["delta"] == "-1.25"
    assert report["artifacts"]["base"]["trades_count"] == 2
    assert report["artifacts"]["candidate"]["equity_points_count"] == 2


def test_compare_backtest_runs_missing_run_directory_fails_cleanly(tmp_path) -> None:
    base_dir = tmp_path / "missing"
    candidate_dir = write_run_dir(tmp_path, "candidate", {"final_equity": "10000"})
    stdout = StringIO()

    exit_code = cli.main(
        ["--base-run-dir", str(base_dir), "--candidate-run-dir", str(candidate_dir)],
        stdout=stdout,
    )

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"run directory does not exist: {base_dir}",
        "result": "FAIL",
    }


def test_compare_backtest_runs_missing_summary_fails_cleanly(tmp_path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    candidate_dir = write_run_dir(tmp_path, "candidate", {"final_equity": "10000"})
    stdout = StringIO()

    exit_code = cli.main(
        ["--base-run-dir", str(base_dir), "--candidate-run-dir", str(candidate_dir)],
        stdout=stdout,
    )

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"summary.json does not exist: {base_dir / 'summary.json'}",
        "result": "FAIL",
    }


def test_compare_backtest_runs_marks_missing_optional_metrics_unavailable(tmp_path) -> None:
    base_dir = write_run_dir(tmp_path, "base", {"final_equity": "10000", "win_rate_pct": None})
    candidate_dir = write_run_dir(tmp_path, "candidate", {"final_equity": "10010"})
    stdout = StringIO()

    exit_code = cli.main(
        ["--base-run-dir", str(base_dir), "--candidate-run-dir", str(candidate_dir)],
        stdout=stdout,
    )

    assert exit_code == 0
    report = json.loads(stdout.getvalue())
    assert report["metrics"]["final_equity"]["delta"] == "10"
    assert report["metrics"]["win_rate_pct"] == {
        "available": False,
        "base": None,
        "candidate": None,
        "delta": None,
        "reason": "metric missing or null",
    }
    assert report["metrics"]["fees_paid"]["available"] is False


def test_compare_backtest_runs_writes_output_json(tmp_path) -> None:
    base_dir = write_run_dir(tmp_path, "base", {"final_equity": "10000"})
    candidate_dir = write_run_dir(tmp_path, "candidate", {"final_equity": "10010"})
    output_path = tmp_path / "reports" / "comparison.json"
    stdout = StringIO()

    exit_code = cli.main(
        [
            "--base-run-dir",
            str(base_dir),
            "--candidate-run-dir",
            str(candidate_dir),
            "--output-json",
            str(output_path),
        ],
        stdout=stdout,
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == json.loads(stdout.getvalue())


def test_compare_backtest_runs_compact_stdout(tmp_path) -> None:
    base_dir = write_run_dir(tmp_path, "base", {"final_equity": "10000", "trades_count": 2})
    candidate_dir = write_run_dir(tmp_path, "candidate", {"final_equity": "10025", "trades_count": 3})
    stdout = StringIO()

    exit_code = cli.main(
        ["--base-run-dir", str(base_dir), "--candidate-run-dir", str(candidate_dir), "--compact"],
        stdout=stdout,
    )

    assert exit_code == 0
    report = json.loads(stdout.getvalue())
    assert report["result"] == "PASS"
    assert report["deltas"]["final_equity"] == "25"
    assert report["deltas"]["trades_count"] == "1"
    assert "metrics" not in report
    assert "artifacts" not in report
    assert "final_balance" in report["unavailable_metrics"]


def test_compare_backtest_runs_many_ranks_saved_artifacts(tmp_path) -> None:
    low_drawdown_dir = write_run_dir(
        tmp_path,
        "low_drawdown",
        {
            "strategy_type": "moving_average_crossover",
            "fast_window": "2",
            "slow_window": "3",
            "starting_balance": "10000",
            "ending_balance": "10050",
            "total_return": "50",
            "max_drawdown_pct": "0.5",
        },
    )
    high_return_dir = write_run_dir(
        tmp_path,
        "high_return",
        {
            "strategy_type": "price_threshold",
            "entry_below": "95",
            "exit_above": "105",
            "starting_balance": "10000",
            "ending_balance": "10100",
            "total_return": "100",
            "max_drawdown_pct": "2",
        },
    )
    middle_dir = write_run_dir(
        tmp_path,
        "middle",
        {
            "strategy_type": "price_threshold",
            "starting_balance": "10000",
            "ending_balance": "10075",
            "total_return": "75",
            "max_drawdown_pct": "1",
        },
    )
    stdout = StringIO()

    exit_code = cli.main(
        [
            "--run-dir",
            str(low_drawdown_dir),
            "--run-dir",
            str(high_return_dir),
            "--run-dir",
            str(middle_dir),
        ],
        stdout=stdout,
    )

    assert exit_code == 0
    report = json.loads(stdout.getvalue())
    assert report["result"] == "PASS"
    assert report["runs_count"] == 3
    assert report["ranking_metrics"] == ["overall_score", "total_return", "ending_balance", "max_drawdown_pct"]
    assert [item["run_name"] for item in report["runs"]] == [
        "low_drawdown",
        "middle",
        "high_return",
    ]
    assert [item["run_name"] for item in report["rankings"]["overall_score"]] == [
        "low_drawdown",
        "middle",
        "high_return",
    ]
    assert [item["run_name"] for item in report["rankings"]["total_return"]] == [
        "high_return",
        "middle",
        "low_drawdown",
    ]
    assert [item["run_name"] for item in report["rankings"]["ending_balance"]] == [
        "high_return",
        "middle",
        "low_drawdown",
    ]
    assert [item["run_name"] for item in report["rankings"]["max_drawdown_pct"]] == [
        "low_drawdown",
        "middle",
        "high_return",
    ]
    assert "overall_score" in report["runs"][0]
    assert "score_components" in report["runs"][0]
    assert "score_warnings" in report["runs"][0]
    low_drawdown = next(item for item in report["runs"] if item["run_name"] == "low_drawdown")
    assert low_drawdown["summary"]["strategy_type"] == "moving_average_crossover"
    assert low_drawdown["summary"]["fast_window"] == "2"


def test_compare_backtest_runs_many_derives_metrics_from_older_artifacts(tmp_path) -> None:
    base_dir = write_run_dir(tmp_path, "base", {"initial_balance": "10000"})
    candidate_dir = write_run_dir(tmp_path, "candidate", {"initial_balance": "10000"})
    write_csv(
        candidate_dir / "trades.csv",
        ["timestamp", "side", "realized_pnl"],
        [
            ["2025-01-01T00:00:00Z", "buy", ""],
            ["2025-01-01T01:00:00Z", "sell", "12.5"],
            ["2025-01-01T02:00:00Z", "buy", ""],
            ["2025-01-01T03:00:00Z", "sell", "-2.5"],
            ["2025-01-01T04:00:00Z", "buy", ""],
            ["2025-01-01T05:00:00Z", "sell", "0"],
        ],
    )
    write_csv(
        candidate_dir / "equity_curve.csv",
        ["timestamp", "equity"],
        [
            ["2025-01-01T00:00:00Z", "10000"],
            ["2025-01-01T01:00:00Z", "10100"],
            ["2025-01-01T02:00:00Z", "10050"],
            ["2025-01-01T03:00:00Z", "10080"],
            ["2025-01-01T04:00:00Z", "10080"],
            ["2025-01-01T05:00:00Z", "10080"],
        ],
    )
    stdout = StringIO()

    exit_code = cli.main(["--run-dir", str(base_dir), "--run-dir", str(candidate_dir)], stdout=stdout)

    assert exit_code == 0
    report = json.loads(stdout.getvalue())
    candidate = next(item for item in report["runs"] if item["run_name"] == "candidate")
    assert candidate["summary"]["ending_balance"] == "10080"
    assert candidate["summary"]["total_return"] == "80"
    assert candidate["summary"]["completed_round_trips"] == 3
    assert candidate["summary"]["realized_pnl"] == "10"
    assert candidate["summary"]["win_count"] == 1
    assert candidate["summary"]["loss_count"] == 1
    assert candidate["summary"]["breakeven_count"] == 1
    assert candidate["summary"]["win_rate_pct"] == "33.33333333333333333333333333"
    assert candidate["summary"]["average_winning_trade_pnl"] == "12.5"
    assert candidate["summary"]["average_losing_trade_pnl"] == "-2.5"
    assert candidate["summary"]["average_trade_pnl"] == "3.333333333333333333333333333"
    assert candidate["summary"]["best_trade_pnl"] == "12.5"
    assert candidate["summary"]["worst_trade_pnl"] == "-2.5"
    assert candidate["summary"]["profit_factor"] == "5"
    assert candidate["summary"]["max_drawdown_amount"] == "50"
    assert candidate["summary"]["max_drawdown_pct"] == "0.495049504950495049504950495"
    assert _decimal(candidate["overall_score"]) > 0
    assert candidate["score_components"]["final_normalized_score"] == candidate["overall_score"]


def test_compare_backtest_runs_many_scores_profitable_lower_risk_run_higher(tmp_path) -> None:
    better_dir = write_run_dir(
        tmp_path,
        "better",
        {
            "starting_balance": "10000",
            "ending_balance": "10200",
            "total_return": "200",
            "total_return_pct": "2",
            "completed_round_trips": 12,
            "win_rate_pct": "70",
            "profit_factor": "2",
            "max_drawdown_pct": "1",
            "exposure_pct": "50",
        },
    )
    worse_dir = write_run_dir(
        tmp_path,
        "worse",
        {
            "starting_balance": "10000",
            "ending_balance": "10100",
            "total_return": "100",
            "total_return_pct": "1",
            "completed_round_trips": 12,
            "win_rate_pct": "55",
            "profit_factor": "1.2",
            "max_drawdown_pct": "12",
            "exposure_pct": "95",
        },
    )
    stdout = StringIO()

    exit_code = cli.main(["--run-dir", str(worse_dir), "--run-dir", str(better_dir)], stdout=stdout)

    assert exit_code == 0
    report = json.loads(stdout.getvalue())
    assert [item["run_name"] for item in report["rankings"]["overall_score"]] == ["better", "worse"]
    better = report["runs"][0]
    worse = report["runs"][1]
    assert better["run_name"] == "better"
    assert _decimal(better["overall_score"]) > _decimal(worse["overall_score"])
    assert set(better["score_components"]) == {
        "return_score",
        "drawdown_score",
        "profit_factor_score",
        "win_rate_score",
        "trade_count_score",
        "exposure_score",
        "final_normalized_score",
    }


def test_compare_backtest_runs_many_scores_negative_high_drawdown_run_lower(tmp_path) -> None:
    steady_dir = write_run_dir(
        tmp_path,
        "steady",
        {
            "starting_balance": "10000",
            "ending_balance": "10050",
            "total_return": "50",
            "total_return_pct": "0.5",
            "completed_round_trips": 10,
            "win_rate_pct": "55",
            "profit_factor": "1.3",
            "max_drawdown_pct": "2",
        },
    )
    risky_dir = write_run_dir(
        tmp_path,
        "risky",
        {
            "starting_balance": "10000",
            "ending_balance": "9800",
            "total_return": "-200",
            "total_return_pct": "-2",
            "completed_round_trips": 10,
            "win_rate_pct": "35",
            "profit_factor": "0.6",
            "max_drawdown_pct": "25",
        },
    )

    stdout = StringIO()
    exit_code = cli.main(["--run-dir", str(risky_dir), "--run-dir", str(steady_dir)], stdout=stdout)

    assert exit_code == 0
    report = json.loads(stdout.getvalue())
    assert [item["run_name"] for item in report["rankings"]["overall_score"]] == ["steady", "risky"]
    risky = next(item for item in report["runs"] if item["run_name"] == "risky")
    assert "negative_return" in risky["score_warnings"]
    assert "high_drawdown" in risky["score_warnings"]


def test_compare_backtest_runs_many_scores_no_trade_run_low_with_warning(tmp_path) -> None:
    active_dir = write_run_dir(
        tmp_path,
        "active",
        {
            "starting_balance": "10000",
            "ending_balance": "10020",
            "total_return": "20",
            "total_return_pct": "0.2",
            "completed_round_trips": 6,
            "win_rate_pct": "60",
            "profit_factor": "1.5",
            "max_drawdown_pct": "2",
        },
    )
    idle_dir = write_run_dir(
        tmp_path,
        "idle",
        {
            "starting_balance": "10000",
            "ending_balance": "10000",
            "total_return": "0",
            "total_return_pct": "0",
            "trades_count": 0,
            "max_drawdown_pct": "0",
        },
    )
    (idle_dir / "trades.csv").unlink()

    stdout = StringIO()
    exit_code = cli.main(["--run-dir", str(idle_dir), "--run-dir", str(active_dir)], stdout=stdout)

    assert exit_code == 0
    report = json.loads(stdout.getvalue())
    idle = next(item for item in report["runs"] if item["run_name"] == "idle")
    assert _decimal(idle["overall_score"]) <= 20
    assert "no_trades" in idle["score_warnings"]
    assert report["rankings"]["overall_score"][-1]["run_name"] == "idle"


def test_compare_backtest_runs_many_warns_on_too_few_trades(tmp_path) -> None:
    few_dir = write_run_dir(
        tmp_path,
        "few",
        {
            "starting_balance": "10000",
            "ending_balance": "10030",
            "total_return": "30",
            "total_return_pct": "0.3",
            "completed_round_trips": 2,
            "win_rate_pct": "100",
            "profit_factor": "3",
            "max_drawdown_pct": "0.5",
        },
    )
    enough_dir = write_run_dir(
        tmp_path,
        "enough",
        {
            "starting_balance": "10000",
            "ending_balance": "10030",
            "total_return": "30",
            "total_return_pct": "0.3",
            "completed_round_trips": 10,
            "win_rate_pct": "60",
            "profit_factor": "1.5",
            "max_drawdown_pct": "0.5",
        },
    )

    stdout = StringIO()
    exit_code = cli.main(["--run-dir", str(few_dir), "--run-dir", str(enough_dir)], stdout=stdout)

    assert exit_code == 0
    few = next(item for item in json.loads(stdout.getvalue())["runs"] if item["run_name"] == "few")
    assert "too_few_trades" in few["score_warnings"]
    assert _decimal(few["overall_score"]) <= 60


def test_compare_backtest_runs_many_tie_breaks_overall_score_deterministically(tmp_path) -> None:
    z_dir = write_run_dir(
        tmp_path,
        "z_run",
        {
            "starting_balance": "10000",
            "ending_balance": "10050",
            "total_return": "50",
            "total_return_pct": "0.5",
            "completed_round_trips": 10,
            "win_rate_pct": "50",
            "profit_factor": "1",
            "max_drawdown_pct": "1",
        },
    )
    a_dir = write_run_dir(
        tmp_path,
        "a_run",
        {
            "starting_balance": "10000",
            "ending_balance": "10050",
            "total_return": "50",
            "total_return_pct": "0.5",
            "completed_round_trips": 10,
            "win_rate_pct": "50",
            "profit_factor": "1",
            "max_drawdown_pct": "1",
        },
    )

    stdout = StringIO()
    exit_code = cli.main(["--run-dir", str(z_dir), "--run-dir", str(a_dir)], stdout=stdout)

    assert exit_code == 0
    report = json.loads(stdout.getvalue())
    assert [item["run_name"] for item in report["rankings"]["overall_score"]] == ["a_run", "z_run"]
    assert [item["run_name"] for item in report["runs"]] == ["a_run", "z_run"]


def test_compare_backtest_runs_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    base_dir = write_run_dir(tmp_path, "base", {"final_equity": "10000"})
    candidate_dir = write_run_dir(tmp_path, "candidate", {"final_equity": "10010"})

    assert cli.main(["--base-run-dir", str(base_dir), "--candidate-run-dir", str(candidate_dir)], stdout=StringIO()) == 0

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


def _decimal(value):
    from decimal import Decimal

    return Decimal(str(value))
