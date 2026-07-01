import json
from io import StringIO

from app.cli import list_backtest_artifacts as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.services.backtest_artifact_catalog import build_backtest_artifact_catalog


def test_backtest_artifact_catalog_lists_runs_reports_sweeps_and_validation_outputs(tmp_path) -> None:
    root = tmp_path / "runs"
    write_run(root, "z_run")
    write_sweep(root, "a_sweep")
    write_comparison_report(root / "reports" / "comparison_report.json")
    write_markdown(root / "reports" / "comparison_report.md")
    write_validation_output(root / "a_sweep" / "sweep_validation.json")

    catalog = build_backtest_artifact_catalog(root)

    assert catalog["schema_version"] == "1"
    assert catalog["artifact_root"] == "runs"
    assert catalog["run_count"] == 1
    assert catalog["comparison_report_count"] == 1
    assert catalog["sweep_count"] == 1
    assert catalog["markdown_report_count"] == 1
    assert catalog["json_report_count"] == 2
    assert catalog["artifact_count"] == 5
    assert [item["artifact_type"] for item in catalog["artifacts"]] == [
        "comparison_report",
        "markdown_report",
        "run",
        "sweep",
        "validation_output",
    ]
    assert catalog["artifacts"][2] == {
        "acceptance_status": None,
        "artifact_type": "run",
        "executive_decision": None,
        "has_manifest": False,
        "has_summary": True,
        "label": "z_run",
        "overall_score": "72.5",
        "recommendation_status": None,
        "relative_path": "z_run",
        "strategy": "price_threshold",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "validation_status": None,
    }
    sweep = catalog["artifacts"][3]
    assert sweep["artifact_type"] == "sweep"
    assert sweep["label"] == "a_sweep"
    assert sweep["overall_score"] == "80"
    assert sweep["recommendation_status"] == "recommended"
    assert sweep["acceptance_status"] == "accepted"
    assert sweep["executive_decision"] == "accept_candidate"
    assert catalog["catalog_warnings"] == []
    assert str(tmp_path.resolve()) not in json.dumps(catalog, sort_keys=True)


def test_backtest_artifact_catalog_filter_and_deterministic_ordering(tmp_path) -> None:
    root = tmp_path / "runs"
    write_run(root, "b_run")
    write_run(root, "a_run")
    write_sweep(root, "c_sweep")

    catalog = build_backtest_artifact_catalog(root, artifact_type="run")

    assert catalog["artifact_count"] == 2
    assert [item["relative_path"] for item in catalog["artifacts"]] == ["a_run", "b_run"]
    assert {item["artifact_type"] for item in catalog["artifacts"]} == {"run"}


def test_backtest_artifact_catalog_warns_on_malformed_artifacts(tmp_path) -> None:
    root = tmp_path / "runs"
    write_run(root, "valid_run")
    malformed = root / "reports" / "broken.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("{not-json\n", encoding="utf-8")

    catalog = build_backtest_artifact_catalog(root)

    assert catalog["artifact_count"] == 1
    assert catalog["catalog_warnings"] == ["malformed_json:reports/broken.json"]


def test_backtest_artifact_catalog_cli_json_output_includes_counts_and_artifacts(tmp_path) -> None:
    root = tmp_path / "runs"
    write_run(root, "demo_run")
    write_sweep(root, "demo_sweep")
    stdout = StringIO()

    exit_code = cli.main(["--artifact-root", str(root), "--json"], stdout=stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["artifact_count"] == 2
    assert payload["run_count"] == 1
    assert payload["sweep_count"] == 1
    assert [item["artifact_type"] for item in payload["artifacts"]] == ["run", "sweep"]
    assert str(tmp_path.resolve()) not in stdout.getvalue()


def test_backtest_artifact_catalog_cli_compact_output(tmp_path) -> None:
    root = tmp_path / "runs"
    write_run(root, "demo_run")
    stdout = StringIO()

    exit_code = cli.main(["--artifact-root", str(root), "--compact"], stdout=stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload == {
        "artifact_count": 1,
        "artifact_root": "runs",
        "artifacts": [
            {
                "artifact_type": "run",
                "label": "demo_run",
                "relative_path": "demo_run",
            }
        ],
        "catalog_warnings": [],
        "comparison_report_count": 0,
        "json_report_count": 0,
        "markdown_report_count": 0,
        "run_count": 1,
        "schema_version": "1",
        "sweep_count": 0,
    }


def test_backtest_artifact_catalog_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    root = tmp_path / "runs"
    write_run(root, "demo_run")

    assert cli.main(["--artifact-root", str(root), "--json"], stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def write_run(root, name: str) -> None:
    run_dir = root / name
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "strategy_type": "price_threshold",
                "overall_score": "72.5",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_sweep(root, name: str) -> None:
    sweep_dir = root / name
    sweep_dir.mkdir(parents=True)
    (sweep_dir / "sweep_summary.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "symbol": "ETHUSDT",
                "timeframe": "4h",
                "strategy_type": "price_threshold",
                "combinations_count": 2,
                "sweep_summary": {
                    "best_overall_score": "80",
                    "recommendation_status": "recommended",
                    "acceptance_status": "accepted",
                    "executive_decision": "accept_candidate",
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_comparison_report(path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "result": "PASS",
                "run_count": 1,
                "runs": [
                    {
                        "run_name": "candidate",
                        "overall_score": "81",
                        "summary": {
                            "symbol": "BTCUSDT",
                            "timeframe": "1h",
                            "strategy_type": "price_threshold",
                        },
                    }
                ],
                "rankings": {},
                "recommendation": {
                    "recommendation_status": "recommended",
                    "acceptance_status": "accepted",
                },
                "executive_summary": {
                    "decision": "accept_candidate",
                    "overall_score": "81",
                    "recommendation_status": "recommended",
                    "acceptance_status": "accepted",
                },
                "export_manifest": {
                    "artifact_type": "backtest_comparison_report",
                    "validation_status": "passed",
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_markdown(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Backtest Comparison Report\n", encoding="utf-8")


def write_validation_output(path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "validation_status": "passed",
                "validation_errors": [],
                "validation_warnings": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
