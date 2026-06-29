import csv
import json
from io import StringIO

from app.cli import run_backtest_demo_pipeline as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


def test_backtest_demo_pipeline_runs_full_flow_from_raw_csv(tmp_path) -> None:
    raw = write_raw_csv(tmp_path)
    work_dir = tmp_path / "pipeline"
    stdout = StringIO()

    exit_code = cli.main(base_args(work_dir) + ["--input", str(raw)], stdout=stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"] == "PASS"
    assert payload["comparison_created"] is False
    assert payload["dataset"]["prepared"] is True
    assert payload["run"]["trades_count"] == 2
    assert payload["artifacts"] == expected_artifacts(work_dir, comparison=False)
    assert (work_dir / "dataset" / "prepared.csv").exists()
    assert (work_dir / "dataset" / "summary.json").exists()
    assert (work_dir / "run" / "summary.json").exists()
    assert (work_dir / "run" / "trades.csv").exists()
    assert (work_dir / "run" / "equity_curve.csv").exists()
    assert (work_dir / "report.md").exists()
    assert (work_dir / "bundle" / "manifest.json").exists()


def test_backtest_demo_pipeline_uses_existing_prepared_csv(tmp_path) -> None:
    prepared = write_prepared_csv(tmp_path)
    work_dir = tmp_path / "pipeline"
    stdout = StringIO()

    exit_code = cli.main(base_args(work_dir) + ["--prepared-csv", str(prepared)], stdout=stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["dataset"]["prepared"] is False
    assert payload["dataset"]["source_prepared_csv"] == str(prepared)
    assert (work_dir / "dataset" / "prepared.csv").read_text(encoding="utf-8") == prepared.read_text(encoding="utf-8")


def test_backtest_demo_pipeline_with_base_run_comparison(tmp_path) -> None:
    raw = write_raw_csv(tmp_path)
    base_run = write_base_run_dir(tmp_path)
    work_dir = tmp_path / "pipeline"
    stdout = StringIO()

    exit_code = cli.main(
        base_args(work_dir) + ["--input", str(raw), "--base-run-dir", str(base_run)],
        stdout=stdout,
    )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["comparison_created"] is True
    assert payload["artifacts"]["comparison_json"] == str(work_dir / "comparison.json")
    comparison = json.loads((work_dir / "comparison.json").read_text(encoding="utf-8"))
    assert comparison["base_run_dir"] == str(base_run)
    assert comparison["candidate_run_dir"] == str(work_dir / "run")
    assert comparison["metrics"]["final_equity"]["available"] is True
    bundle_manifest = json.loads((work_dir / "bundle" / "manifest.json").read_text(encoding="utf-8"))
    assert bundle_manifest["comparison_included"] is True
    assert (work_dir / "bundle" / "comparison.json").exists()


def test_backtest_demo_pipeline_missing_input_fails_cleanly(tmp_path) -> None:
    missing = tmp_path / "missing.csv"
    work_dir = tmp_path / "pipeline"
    stdout = StringIO()

    exit_code = cli.main(base_args(work_dir) + ["--input", str(missing)], stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"input file does not exist: {missing}",
        "result": "FAIL",
    }


def test_backtest_demo_pipeline_refuses_non_empty_work_dir_without_overwrite(tmp_path) -> None:
    raw = write_raw_csv(tmp_path)
    work_dir = tmp_path / "pipeline"
    work_dir.mkdir()
    (work_dir / "old.txt").write_text("old\n", encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.main(base_args(work_dir) + ["--input", str(raw)], stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"work directory is not empty; pass --overwrite to replace: {work_dir}",
        "result": "FAIL",
    }
    assert (work_dir / "old.txt").exists()


def test_backtest_demo_pipeline_overwrite_rebuilds_work_dir(tmp_path) -> None:
    raw = write_raw_csv(tmp_path)
    work_dir = tmp_path / "pipeline"
    work_dir.mkdir()
    (work_dir / "old.txt").write_text("old\n", encoding="utf-8")

    exit_code = cli.main(base_args(work_dir) + ["--input", str(raw), "--overwrite"], stdout=StringIO())

    assert exit_code == 0
    assert not (work_dir / "old.txt").exists()
    assert (work_dir / "bundle" / "manifest.json").exists()


def test_backtest_demo_pipeline_compact_stdout(tmp_path) -> None:
    raw = write_raw_csv(tmp_path)
    work_dir = tmp_path / "pipeline"
    stdout = StringIO()

    exit_code = cli.main(base_args(work_dir) + ["--input", str(raw), "--compact"], stdout=stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload == {
        "artifacts": expected_artifacts(work_dir, comparison=False),
        "comparison_created": False,
        "result": "PASS",
    }


def test_backtest_demo_pipeline_expected_artifact_paths(tmp_path) -> None:
    raw = write_raw_csv(tmp_path)
    work_dir = tmp_path / "pipeline"

    assert cli.main(base_args(work_dir) + ["--input", str(raw)], stdout=StringIO()) == 0

    assert sorted(path.relative_to(work_dir).as_posix() for path in work_dir.rglob("*") if path.is_file()) == [
        "bundle/README.md",
        "bundle/equity_curve.csv",
        "bundle/manifest.json",
        "bundle/report.md",
        "bundle/summary.json",
        "bundle/trades.csv",
        "dataset/prepared.csv",
        "dataset/summary.json",
        "report.md",
        "run/equity_curve.csv",
        "run/summary.json",
        "run/trades.csv",
    ]


def test_backtest_demo_pipeline_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    raw = write_raw_csv(tmp_path)

    assert cli.main(base_args(tmp_path / "pipeline") + ["--input", str(raw)], stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def write_raw_csv(tmp_path):
    path = tmp_path / "raw.csv"
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


def write_prepared_csv(tmp_path):
    path = tmp_path / "prepared.csv"
    path.write_text(write_raw_csv(tmp_path).read_text(encoding="utf-8"), encoding="utf-8")
    return path


def write_base_run_dir(tmp_path):
    run_dir = tmp_path / "base_run"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"final_equity": "10000", "trades_count": 1, "total_return_pct": "0"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_csv(run_dir / "trades.csv", ["timestamp", "side"], [["2025-01-01T00:00:00Z", "buy"]])
    write_csv(run_dir / "equity_curve.csv", ["timestamp", "equity"], [["2025-01-01T00:00:00Z", "10000"]])
    return run_dir


def write_csv(path, fieldnames: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)


def base_args(work_dir):
    return [
        "--symbol",
        "BTCUSDT",
        "--timeframe",
        "1h",
        "--work-dir",
        str(work_dir),
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


def expected_artifacts(work_dir, *, comparison: bool):
    return {
        "bundle_dir": str(work_dir / "bundle"),
        "bundle_manifest": str(work_dir / "bundle" / "manifest.json"),
        "comparison_json": str(work_dir / "comparison.json") if comparison else None,
        "dataset_summary": str(work_dir / "dataset" / "summary.json"),
        "equity_curve_csv": str(work_dir / "run" / "equity_curve.csv"),
        "prepared_csv": str(work_dir / "dataset" / "prepared.csv"),
        "report_md": str(work_dir / "report.md"),
        "run_dir": str(work_dir / "run"),
        "run_summary": str(work_dir / "run" / "summary.json"),
        "trades_csv": str(work_dir / "run" / "trades.csv"),
        "work_dir": str(work_dir),
    }
