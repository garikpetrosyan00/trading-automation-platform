import csv
import hashlib
import json
from io import StringIO

from app.cli import export_backtest_demo_bundle as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


def test_export_backtest_demo_bundle_copies_artifacts_and_manifest(tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run")
    output_dir = tmp_path / "bundle"
    stdout = StringIO()

    exit_code = cli.main(
        ["--run-dir", str(run_dir), "--output-dir", str(output_dir), "--title", "BTCUSDT Demo"],
        stdout=stdout,
    )

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {
        "comparison_included": False,
        "files_count": 5,
        "output_dir": str(output_dir),
        "report_included": False,
        "result": "PASS",
    }
    assert (output_dir / "summary.json").read_text(encoding="utf-8") == (run_dir / "summary.json").read_text(encoding="utf-8")
    assert (output_dir / "trades.csv").exists()
    assert (output_dir / "equity_curve.csv").exists()
    assert (output_dir / "README.md").exists()

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["title"] == "BTCUSDT Demo"
    assert manifest["source_run_dir"] == str(run_dir)
    assert manifest["comparison_included"] is False
    assert manifest["report_included"] is False
    assert manifest["unavailable"] == []
    files_by_name = {file["name"]: file for file in manifest["files"]}
    assert sorted(files_by_name) == ["README.md", "equity_curve.csv", "manifest.json", "summary.json", "trades.csv"]
    assert files_by_name["trades.csv"]["rows"] == 2
    assert files_by_name["equity_curve.csv"]["rows"] == 3
    assert files_by_name["summary.json"]["sha256"] == sha256(output_dir / "summary.json")
    assert files_by_name["manifest.json"]["sha256"] is None


def test_export_backtest_demo_bundle_missing_run_directory_fails_cleanly(tmp_path) -> None:
    missing_dir = tmp_path / "missing"
    stdout = StringIO()

    exit_code = cli.main(
        ["--run-dir", str(missing_dir), "--output-dir", str(tmp_path / "bundle")],
        stdout=stdout,
    )

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"run directory does not exist: {missing_dir}",
        "result": "FAIL",
    }


def test_export_backtest_demo_bundle_missing_summary_fails_cleanly(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stdout = StringIO()

    exit_code = cli.main(["--run-dir", str(run_dir), "--output-dir", str(tmp_path / "bundle")], stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"summary.json does not exist: {run_dir / 'summary.json'}",
        "result": "FAIL",
    }


def test_export_backtest_demo_bundle_marks_missing_optional_run_artifacts(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(json.dumps({"result": "PASS"}) + "\n", encoding="utf-8")
    output_dir = tmp_path / "bundle"

    assert cli.main(["--run-dir", str(run_dir), "--output-dir", str(output_dir)], stdout=StringIO()) == 0

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert sorted(file["name"] for file in manifest["files"]) == ["README.md", "manifest.json", "summary.json"]
    assert manifest["unavailable"] == [
        {"file": "trades.csv", "reason": "not available", "source": str(run_dir / "trades.csv")},
        {
            "file": "equity_curve.csv",
            "reason": "not available",
            "source": str(run_dir / "equity_curve.csv"),
        },
    ]
    assert "trades.csv" not in {path.name for path in output_dir.iterdir()}


def test_export_backtest_demo_bundle_includes_comparison_and_report(tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run")
    comparison_json = tmp_path / "comparison.json"
    comparison_json.write_text(json.dumps({"result": "PASS", "deltas": {"final_equity": "10"}}) + "\n", encoding="utf-8")
    report_md = tmp_path / "report.md"
    report_md.write_text("# Report\n", encoding="utf-8")
    output_dir = tmp_path / "bundle"

    assert (
        cli.main(
            [
                "--run-dir",
                str(run_dir),
                "--comparison-json",
                str(comparison_json),
                "--report-md",
                str(report_md),
                "--output-dir",
                str(output_dir),
            ],
            stdout=StringIO(),
        )
        == 0
    )

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["comparison_included"] is True
    assert manifest["report_included"] is True
    assert (output_dir / "comparison.json").read_text(encoding="utf-8") == comparison_json.read_text(encoding="utf-8")
    assert (output_dir / "report.md").read_text(encoding="utf-8") == "# Report\n"
    assert "comparison.json" in {file["name"] for file in manifest["files"]}
    assert "report.md" in {file["name"] for file in manifest["files"]}


def test_export_backtest_demo_bundle_missing_optional_inputs_are_unavailable(tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run")
    missing_comparison = tmp_path / "missing_comparison.json"
    missing_report = tmp_path / "missing_report.md"
    output_dir = tmp_path / "bundle"

    assert (
        cli.main(
            [
                "--run-dir",
                str(run_dir),
                "--comparison-json",
                str(missing_comparison),
                "--report-md",
                str(missing_report),
                "--output-dir",
                str(output_dir),
            ],
            stdout=StringIO(),
        )
        == 0
    )

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["comparison_included"] is False
    assert manifest["report_included"] is False
    assert {"file": "comparison.json", "reason": "not available", "source": str(missing_comparison)} in manifest["unavailable"]
    assert {"file": "report.md", "reason": "not available", "source": str(missing_report)} in manifest["unavailable"]


def test_export_backtest_demo_bundle_refuses_non_empty_output_without_overwrite(tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run")
    output_dir = tmp_path / "bundle"
    output_dir.mkdir()
    (output_dir / "old.txt").write_text("old\n", encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.main(["--run-dir", str(run_dir), "--output-dir", str(output_dir)], stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output directory is not empty; pass --overwrite to replace: {output_dir}",
        "result": "FAIL",
    }
    assert (output_dir / "old.txt").exists()


def test_export_backtest_demo_bundle_overwrite_rebuilds_output(tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run")
    output_dir = tmp_path / "bundle"
    output_dir.mkdir()
    (output_dir / "old.txt").write_text("old\n", encoding="utf-8")

    exit_code = cli.main(
        ["--run-dir", str(run_dir), "--output-dir", str(output_dir), "--overwrite"],
        stdout=StringIO(),
    )

    assert exit_code == 0
    assert not (output_dir / "old.txt").exists()
    assert (output_dir / "manifest.json").exists()


def test_export_backtest_demo_bundle_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    run_dir = write_run_dir(tmp_path, "run")

    assert cli.main(["--run-dir", str(run_dir), "--output-dir", str(tmp_path / "bundle")], stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def write_run_dir(tmp_path, name: str):
    run_dir = tmp_path / name
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"result": "PASS", "symbol": "BTCUSDT", "final_equity": "10010"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_csv(run_dir / "trades.csv", ["timestamp", "side"], [["2025-01-01T00:00:00Z", "buy"], ["2025-01-01T01:00:00Z", "sell"]])
    write_csv(
        run_dir / "equity_curve.csv",
        ["timestamp", "equity"],
        [
            ["2025-01-01T00:00:00Z", "10000"],
            ["2025-01-01T01:00:00Z", "10005"],
            ["2025-01-01T02:00:00Z", "10010"],
        ],
    )
    return run_dir


def write_csv(path, fieldnames: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)


def sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()
