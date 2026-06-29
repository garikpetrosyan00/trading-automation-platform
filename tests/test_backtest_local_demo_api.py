import json

from fastapi.testclient import TestClient

from app.api.v1.endpoints.local_backtest_artifacts import get_local_backtest_artifact_service
from app.main import app
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.services.local_backtest_artifacts import LocalBacktestArtifactService


def test_local_demo_api_reads_summary_json(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_run_artifacts(runs_root, "demo_001")
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/runs/demo_001/summary")
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "artifact": "summary",
        "run_name": "demo_001",
        "summary": {
            "result": "PASS",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "final_equity": "10010",
            "trades_count": 2,
        },
    }


def test_local_demo_api_reads_report_markdown(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_run_artifacts(runs_root, "demo_001")
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/runs/demo_001/report")
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# Demo Report" in response.text
    assert str(tmp_path.resolve()) not in response.text


def test_local_demo_api_reads_bundle_manifest_json(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_bundle_artifacts(runs_root, "demo_bundle")
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/bundles/demo_bundle/manifest")
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "artifact": "manifest",
        "bundle_name": "demo_bundle",
        "manifest": {
            "comparison_included": True,
            "files": [
                {"name": "summary.json", "rows": None, "sha256": "abc", "size_bytes": 10},
            ],
            "report_included": True,
            "title": "Demo Bundle",
            "unavailable": [{"file": "report.md", "reason": "not available"}],
        },
    }


def test_local_demo_api_missing_artifact_returns_clean_404(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    override_local_artifact_service(tmp_path / "runs")

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/runs/missing/summary")
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 404
    assert response.json() == {"detail": "Local backtest artifact not found", "error_code": "artifact_not_found"}


def test_local_demo_api_rejects_path_traversal(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    override_local_artifact_service(tmp_path / "runs")

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/runs/..secret/summary")
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid local backtest artifact name", "error_code": "invalid_artifact_name"}


def test_local_demo_api_does_not_touch_runtime_audit_tables(
    db_session,
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_run_artifacts(runs_root, "demo_001")
    write_bundle_artifacts(runs_root, "demo_bundle")
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/backtests/local-demo/runs/demo_001/summary").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/runs/demo_001/report").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/bundles/demo_bundle/manifest").status_code == 200
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def override_local_artifact_service(runs_root):
    app.dependency_overrides[get_local_backtest_artifact_service] = lambda: LocalBacktestArtifactService(runs_root)


def write_run_artifacts(runs_root, run_name: str) -> None:
    run_dir = runs_root / run_name
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "final_equity": "10010",
                "trades_count": 2,
                "prepared_csv": "/private/source.csv",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text("# Demo Report\n\nSource: " + str(runs_root.resolve()) + "\n", encoding="utf-8")


def write_bundle_artifacts(runs_root, bundle_name: str) -> None:
    bundle_dir = runs_root / bundle_name
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "manifest.json").write_text(
        json.dumps(
            {
                "title": "Demo Bundle",
                "comparison_included": True,
                "report_included": True,
                "source_run_dir": "/private/run",
                "files": [
                    {"name": "summary.json", "sha256": "abc", "rows": None, "size_bytes": 10},
                ],
                "unavailable": [
                    {"file": "report.md", "source": "/private/report.md", "reason": "not available"},
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
