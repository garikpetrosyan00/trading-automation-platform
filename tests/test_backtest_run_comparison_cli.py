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
