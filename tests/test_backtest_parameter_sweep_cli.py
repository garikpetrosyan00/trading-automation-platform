import csv
import json
from io import StringIO

import pytest

from app.cli import run_backtest_parameter_sweep as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


def test_backtest_parameter_sweep_writes_outputs_and_per_run_artifacts(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    stdout = StringIO()

    exit_code = cli.main(base_args(path, output_dir), stdout=stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"] == "PASS"
    assert payload["combinations_count"] == 4
    assert payload["ranking_metric"] == "final_equity"
    assert "not a profitability guarantee" in payload["profitability_note"]
    assert (output_dir / "sweep_summary.json").exists()
    assert (output_dir / "sweep_results.csv").exists()
    assert (output_dir / "sweep_report.md").exists()
    run_dirs = sorted(path.name for path in output_dir.iterdir() if path.is_dir())
    assert run_dirs == [
        "run_001_entry_95_exit_105",
        "run_002_entry_95_exit_107",
        "run_003_entry_105_exit_105",
        "run_004_entry_105_exit_107",
    ]
    assert all((output_dir / run_dir / "summary.json").exists() for run_dir in run_dirs)
    assert all((output_dir / run_dir / "trades.csv").exists() for run_dir in run_dirs)
    assert all((output_dir / run_dir / "equity_curve.csv").exists() for run_dir in run_dirs)


def test_backtest_parameter_sweep_multiple_combinations_and_deterministic_ranking(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"

    assert cli.main(base_args(path, output_dir), stdout=StringIO()) == 0

    summary = json.loads((output_dir / "sweep_summary.json").read_text(encoding="utf-8"))
    ranked = summary["results"]
    assert [row["rank"] for row in ranked] == [1, 2, 3, 4]
    assert ranked[0]["entry_below"] == "95"
    assert ranked[0]["exit_above"] == "107"
    assert ranked[0]["final_equity"] == "10017"
    assert ranked[-1]["entry_below"] == "105"
    assert ranked[-1]["exit_above"] == "105"
    assert ranked[-1]["final_equity"] == "10006"


def test_backtest_parameter_sweep_invalid_csv_path_fails_cleanly(tmp_path) -> None:
    missing_path = tmp_path / "missing.csv"
    output_dir = tmp_path / "sweep"
    stdout = StringIO()

    exit_code = cli.main(base_args(missing_path, output_dir), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"CSV file does not exist: {missing_path}",
        "result": "FAIL",
    }


@pytest.mark.parametrize(
    ("extra_args", "expected_error"),
    [
        (["--entry-below-values", "95,not-a-number"], "entry-below-values must be a decimal"),
        (["--entry-below-values", "95,"], "entry-below-values must be a comma-separated decimal list"),
        (["--exit-above-values", "0"], "exit-above-values values must be positive"),
        (["--strategy-type", "moving_average_cross"], "unsupported strategy type: moving_average_cross"),
    ],
)
def test_backtest_parameter_sweep_invalid_values_fail_cleanly(tmp_path, extra_args, expected_error) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    stdout = StringIO()

    exit_code = cli.main(replace_args(base_args(path, output_dir), extra_args), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {"error": expected_error, "result": "FAIL"}


def test_backtest_parameter_sweep_refuses_non_empty_output_without_overwrite(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    output_dir.mkdir()
    (output_dir / "old.txt").write_text("old\n", encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.main(base_args(path, output_dir), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output directory is not empty; pass --overwrite to replace: {output_dir}",
        "result": "FAIL",
    }
    assert (output_dir / "old.txt").exists()


def test_backtest_parameter_sweep_overwrite_rebuilds_output(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    output_dir.mkdir()
    (output_dir / "old.txt").write_text("old\n", encoding="utf-8")

    exit_code = cli.main(base_args(path, output_dir) + ["--overwrite"], stdout=StringIO())

    assert exit_code == 0
    assert not (output_dir / "old.txt").exists()
    assert (output_dir / "sweep_summary.json").exists()


def test_backtest_parameter_sweep_results_csv_and_compact_stdout(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    stdout = StringIO()

    exit_code = cli.main(base_args(path, output_dir) + ["--compact"], stdout=stdout)

    assert exit_code == 0
    printed = json.loads(stdout.getvalue())
    assert printed == {
        "best_result": {
            "entry_below": "95",
            "exit_above": "107",
            "fees_paid": "0",
            "final_equity": "10017",
            "max_drawdown_pct": "0",
            "rank": 1,
            "run_name": "run_002_entry_95_exit_107",
            "summary_path": str(output_dir / "run_002_entry_95_exit_107" / "summary.json"),
            "total_return_pct": "0.17",
            "trades_count": 2,
            "win_rate_pct": "100",
        },
        "combinations_count": 4,
        "ranking_metric": "final_equity",
        "result": "PASS",
        "strategy_type": "price_threshold",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
    }
    with (output_dir / "sweep_results.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["rank"] == "1"
    assert rows[0]["run_name"] == "run_002_entry_95_exit_107"
    assert rows[0]["final_equity"] == "10017"


def test_backtest_parameter_sweep_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"

    assert cli.main(base_args(path, output_dir), stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def write_sweep_csv(tmp_path):
    path = tmp_path / "prepared.csv"
    path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2025-01-01T00:00:00Z,100,101,99,100,1",
                "2025-01-01T01:00:00Z,94,95,93,94,1",
                "2025-01-01T02:00:00Z,106,107,105,106,1",
                "2025-01-01T03:00:00Z,111,112,110,111,1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def base_args(path, output_dir):
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
        "0",
        "--strategy-type",
        "price_threshold",
        "--entry-below-values",
        "95,105",
        "--exit-above-values",
        "105,107",
        "--order-quantity",
        "1",
        "--output-dir",
        str(output_dir),
    ]


def replace_args(args: list[str], replacements: list[str]) -> list[str]:
    updated = list(args)
    for flag, value in zip(replacements[0::2], replacements[1::2]):
        index = updated.index(flag)
        updated[index + 1] = value
    return updated
