import csv
import json
from io import StringIO
from pathlib import Path

from app.cli import run_prepared_backtest_smoke as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


def test_prepared_backtest_smoke_runs_dataset_and_writes_outputs(tmp_path) -> None:
    path = write_prepared_csv(tmp_path)
    output_dir = tmp_path / "data" / "backtests" / "runs" / "demo_001"
    stdout = StringIO()

    exit_code = cli.main(base_args(path) + ["--output-dir", str(output_dir)], stdout=stdout)

    assert exit_code == 0
    printed = json.loads(stdout.getvalue())
    assert printed["result"] == "PASS"
    assert printed["prepared_csv"] == str(path)
    assert printed["output_dir"] == str(output_dir)
    assert "trades" not in printed
    assert "equity_curve" not in printed

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["result"] == "PASS"
    assert summary["prepared_csv"] == str(path)
    assert summary["output_dir"] == str(output_dir)
    assert "trades" not in summary
    assert "equity_curve" not in summary
    with (output_dir / "trades.csv").open(newline="", encoding="utf-8") as handle:
        trades = list(csv.DictReader(handle))
    with (output_dir / "equity_curve.csv").open(newline="", encoding="utf-8") as handle:
        equity_curve = list(csv.DictReader(handle))
    assert [trade["side"] for trade in trades] == ["buy", "sell"]
    assert [point["close_price"] for point in equity_curve] == ["90", "110"]


def test_prepared_backtest_smoke_missing_csv_fails_cleanly(tmp_path) -> None:
    missing_path = tmp_path / "missing.csv"
    stdout = StringIO()

    exit_code = cli.main(base_args(missing_path), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"CSV file does not exist: {missing_path}",
        "result": "FAIL",
    }


def test_prepared_backtest_smoke_refuses_existing_outputs_without_overwrite(tmp_path) -> None:
    path = write_prepared_csv(tmp_path)
    output_dir = tmp_path / "data" / "backtests" / "runs" / "demo_002"
    assert cli.main(base_args(path) + ["--output-dir", str(output_dir)], stdout=StringIO()) == 0
    stdout = StringIO()

    exit_code = cli.main(base_args(path) + ["--output-dir", str(output_dir)], stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": "output files already exist; pass --overwrite to replace: summary.json, trades.csv, equity_curve.csv",
        "result": "FAIL",
    }


def test_prepared_backtest_smoke_overwrite_replaces_outputs(tmp_path) -> None:
    path = write_prepared_csv(tmp_path)
    output_dir = tmp_path / "data" / "backtests" / "runs" / "demo_003"
    output_dir.mkdir(parents=True)
    (output_dir / "summary.json").write_text("old\n", encoding="utf-8")
    (output_dir / "trades.csv").write_text("old\n", encoding="utf-8")
    (output_dir / "equity_curve.csv").write_text("old\n", encoding="utf-8")

    exit_code = cli.main(
        base_args(path) + ["--output-dir", str(output_dir), "--overwrite"],
        stdout=StringIO(),
    )

    assert exit_code == 0
    assert json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))["result"] == "PASS"
    assert "old" not in (output_dir / "trades.csv").read_text(encoding="utf-8")
    assert "old" not in (output_dir / "equity_curve.csv").read_text(encoding="utf-8")


def test_prepared_backtest_smoke_stdout_is_summary_only(tmp_path) -> None:
    path = write_prepared_csv(tmp_path)
    stdout = StringIO()

    exit_code = cli.main(base_args(path), stdout=stdout)

    assert exit_code == 0
    printed = json.loads(stdout.getvalue())
    assert printed["result"] == "PASS"
    assert printed["trades_count"] == 2
    assert "trades" not in printed
    assert "equity_curve" not in printed


def test_prepared_backtest_smoke_compares_with_previous_summary(tmp_path) -> None:
    path = write_prepared_csv(tmp_path)
    previous_summary = tmp_path / "previous_summary.json"
    previous_summary.write_text(
        json.dumps(
            {
                "final_equity": "10010",
                "total_return_pct": "0.1",
                "max_drawdown_pct": "1.5",
                "trades_count": 1,
            }
        ),
        encoding="utf-8",
    )
    stdout = StringIO()

    exit_code = cli.main(base_args(path) + ["--compare-summary", str(previous_summary)], stdout=stdout)

    assert exit_code == 0
    comparison = json.loads(stdout.getvalue())["comparison"]
    assert comparison == {
        "final_equity_delta": "9.8",
        "max_drawdown_pct_delta": "-1.4991",
        "previous_summary_path": str(previous_summary),
        "total_return_pct_delta": "0.098",
        "trades_count_delta": 1,
    }


def test_prepared_backtest_smoke_generated_runs_are_gitignored() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8").splitlines()

    assert "data/backtests/runs/" in gitignore


def test_prepared_backtest_smoke_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    path = write_prepared_csv(tmp_path)

    assert cli.main(base_args(path), stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def write_prepared_csv(tmp_path):
    path = tmp_path / "BTCUSDT_1h_prepared.csv"
    path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2025-01-01T00:00:00Z,100,101,89,90,1",
                "2025-01-01T01:00:00Z,90,111,90,110,1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def base_args(path):
    return [
        "--symbol",
        "BTCUSDT",
        "--timeframe",
        "1h",
        "--csv",
        str(path),
        "--initial-balance",
        "10000",
        "--fee-rate",
        "0.001",
        "--strategy-type",
        "price_threshold",
        "--entry-below",
        "95",
        "--exit-above",
        "105",
        "--order-quantity",
        "1",
    ]
