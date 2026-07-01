import json
from io import StringIO

from app.cli import run_backtest_parameter_sweep, validate_backtest_parameter_sweep as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from tests.test_backtest_parameter_sweep_cli import base_args, write_sweep_csv


def test_validate_backtest_parameter_sweep_accepts_valid_output(tmp_path) -> None:
    sweep_dir = write_valid_sweep(tmp_path)
    stdout = StringIO()

    exit_code = cli.main(["--sweep-dir", str(sweep_dir)], stdout=stdout)

    assert exit_code == 0
    result = json.loads(stdout.getvalue())
    assert result == {
        "checked_artifacts": ["sweep_summary.json", "sweep_results.csv", "sweep_report.md"],
        "checked_row_count": 4,
        "schema_version": "1",
        "validation_errors": [],
        "validation_status": "passed",
        "validation_warnings": [],
    }


def test_validate_backtest_parameter_sweep_missing_markdown_warns(tmp_path) -> None:
    sweep_dir = write_valid_sweep(tmp_path)
    (sweep_dir / "sweep_report.md").unlink()

    exit_code, result = run_validator(sweep_dir)

    assert exit_code == 0
    assert result["validation_status"] == "passed_with_warnings"
    assert result["validation_errors"] == []
    assert result["validation_warnings"] == ["sweep_report_md_missing"]


def test_validate_backtest_parameter_sweep_malformed_summary_fails(tmp_path) -> None:
    sweep_dir = write_valid_sweep(tmp_path)
    summary = read_summary(sweep_dir)
    summary["sweep_summary"]["top_parameter_sets"] = "not-a-list"
    write_summary(sweep_dir, summary)

    exit_code, result = run_validator(sweep_dir)

    assert exit_code == 1
    assert result["validation_status"] == "failed"
    assert "sweep_summary.top_parameter_sets must be a list" in result["validation_errors"]


def test_validate_backtest_parameter_sweep_rejects_nan_and_infinity(tmp_path) -> None:
    sweep_dir = write_valid_sweep(tmp_path)
    summary = read_summary(sweep_dir)
    summary["sweep_summary"]["best_overall_score"] = float("nan")
    summary["sweep_summary"]["top_parameter_sets"][0]["overall_score"] = float("inf")
    (sweep_dir / "sweep_summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")

    exit_code, result = run_validator(sweep_dir)

    assert exit_code == 1
    assert "sweep_summary.json contains NaN or Infinity" in result["validation_errors"]
    assert "sweep_summary.best_overall_score must be finite numeric" in result["validation_errors"]
    assert "sweep_summary.top_parameter_sets[0].overall_score must be finite numeric" in result["validation_errors"]


def test_validate_backtest_parameter_sweep_rejects_inconsistent_counts(tmp_path) -> None:
    sweep_dir = write_valid_sweep(tmp_path)
    summary = read_summary(sweep_dir)
    summary["sweep_summary"]["tested_parameter_count"] = 99
    summary["sweep_summary"]["accepted_count"] = 3
    summary["sweep_summary"]["rejected_count"] = 3
    write_summary(sweep_dir, summary)

    exit_code, result = run_validator(sweep_dir)

    assert exit_code == 1
    assert "sweep_summary.tested_parameter_count must match results length" in result["validation_errors"]
    assert "sweep_summary.tested_parameter_count must match sweep_results.csv row count" in result["validation_errors"]
    assert "sweep_summary accepted_count + rejected_count must not exceed tested_parameter_count" not in result["validation_errors"]


def test_validate_backtest_parameter_sweep_rejects_warning_count_mismatch(tmp_path) -> None:
    sweep_dir = write_valid_sweep(tmp_path)
    summary = read_summary(sweep_dir)
    summary["sweep_summary"]["warning_count"] = 99
    write_summary(sweep_dir, summary)

    exit_code, result = run_validator(sweep_dir)

    assert exit_code == 1
    assert "sweep_summary.warning_count must match warnings length" in result["validation_errors"]


def test_validate_backtest_parameter_sweep_accepts_older_minimal_output_with_warnings(tmp_path) -> None:
    sweep_dir = tmp_path / "old_sweep"
    sweep_dir.mkdir()
    write_summary(
        sweep_dir,
        {
            "result": "PASS",
            "combinations_count": 1,
            "results": [{"run_name": "run_001"}],
        },
    )

    exit_code, result = run_validator(sweep_dir)

    assert exit_code == 0
    assert result["validation_status"] == "passed_with_warnings"
    assert result["validation_errors"] == []
    assert result["checked_row_count"] == 1
    assert result["validation_warnings"] == [
        "sweep_results_csv_missing",
        "sweep_report_md_missing",
        "sweep_summary_missing_compatibility_mode",
    ]


def test_validate_backtest_parameter_sweep_cli_json_includes_validation_fields(tmp_path) -> None:
    sweep_dir = write_valid_sweep(tmp_path)

    exit_code, result = run_validator(sweep_dir)

    assert exit_code == 0
    assert set(result) == {
        "checked_artifacts",
        "checked_row_count",
        "schema_version",
        "validation_errors",
        "validation_status",
        "validation_warnings",
    }
    assert result["validation_status"] == "passed"


def test_validate_backtest_parameter_sweep_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    sweep_dir = write_valid_sweep(tmp_path)

    assert cli.main(["--sweep-dir", str(sweep_dir)], stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def write_valid_sweep(tmp_path):
    csv_path = write_sweep_csv(tmp_path)
    sweep_dir = tmp_path / "sweep"
    assert run_backtest_parameter_sweep.main(base_args(csv_path, sweep_dir), stdout=StringIO()) == 0
    return sweep_dir


def read_summary(sweep_dir):
    return json.loads((sweep_dir / "sweep_summary.json").read_text(encoding="utf-8"))


def write_summary(sweep_dir, payload) -> None:
    (sweep_dir / "sweep_summary.json").write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def run_validator(sweep_dir):
    stdout = StringIO()
    exit_code = cli.main(["--sweep-dir", str(sweep_dir)], stdout=stdout)
    return exit_code, json.loads(stdout.getvalue())
