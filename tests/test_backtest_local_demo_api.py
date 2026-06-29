import json
import csv

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


def test_local_demo_api_lists_available_runs_sorted_and_sanitized(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_run_artifacts(runs_root, "z_run", symbol="ETHUSDT")
    write_run_artifacts(runs_root, "a_run")
    write_incomplete_folder(runs_root, "incomplete")
    write_run_artifacts(runs_root, "..unsafe")
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/runs")
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "name": "a_run",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "artifacts": {
                    "summary_json": True,
                    "report_md": True,
                    "trades_csv": True,
                    "equity_curve_csv": True,
                    "manifest_json": False,
                },
                "row_counts": {"trades": 2, "equity_curve": 2},
            },
            {
                "name": "z_run",
                "symbol": "ETHUSDT",
                "timeframe": "1h",
                "artifacts": {
                    "summary_json": True,
                    "report_md": True,
                    "trades_csv": True,
                    "equity_curve_csv": True,
                    "manifest_json": False,
                },
                "row_counts": {"trades": 2, "equity_curve": 2},
            },
        ]
    }
    assert str(tmp_path.resolve()) not in response.text


def test_local_demo_api_lists_available_bundles_sorted_and_sanitized(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_bundle_artifacts(runs_root, "z_bundle", symbol="ETHUSDT")
    write_bundle_artifacts(runs_root, "a_bundle")
    write_incomplete_folder(runs_root, "empty_bundle")
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/bundles")
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "name": "a_bundle",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "title": "Demo Bundle",
                "comparison_included": True,
                "report_included": True,
                "artifacts": {
                    "summary_json": True,
                    "report_md": False,
                    "trades_csv": True,
                    "equity_curve_csv": True,
                    "manifest_json": True,
                },
                "row_counts": {"trades": 2, "equity_curve": 2},
            },
            {
                "name": "z_bundle",
                "symbol": "ETHUSDT",
                "timeframe": "1h",
                "title": "Demo Bundle",
                "comparison_included": True,
                "report_included": True,
                "artifacts": {
                    "summary_json": True,
                    "report_md": False,
                    "trades_csv": True,
                    "equity_curve_csv": True,
                    "manifest_json": True,
                },
                "row_counts": {"trades": 2, "equity_curve": 2},
            },
        ]
    }
    assert str(tmp_path.resolve()) not in response.text


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
            assert client.get("/api/v1/backtests/local-demo/runs").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/bundles").status_code == 200
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


def write_run_artifacts(runs_root, run_name: str, *, symbol: str = "BTCUSDT") -> None:
    run_dir = runs_root / run_name
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "symbol": symbol,
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
    write_csv(run_dir / "trades.csv", ["timestamp", "side"], [["2025-01-01T00:00:00Z", "buy"], ["2025-01-01T01:00:00Z", "sell"]])
    write_csv(
        run_dir / "equity_curve.csv",
        ["timestamp", "equity"],
        [["2025-01-01T00:00:00Z", "10000"], ["2025-01-01T01:00:00Z", "10010"]],
    )


def write_bundle_artifacts(runs_root, bundle_name: str, *, symbol: str = "BTCUSDT") -> None:
    bundle_dir = runs_root / bundle_name
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "summary.json").write_text(
        json.dumps({"result": "PASS", "symbol": symbol, "timeframe": "1h"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_csv(bundle_dir / "trades.csv", ["timestamp", "side"], [["2025-01-01T00:00:00Z", "buy"], ["2025-01-01T01:00:00Z", "sell"]])
    write_csv(
        bundle_dir / "equity_curve.csv",
        ["timestamp", "equity"],
        [["2025-01-01T00:00:00Z", "10000"], ["2025-01-01T01:00:00Z", "10010"]],
    )
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


def write_incomplete_folder(runs_root, name: str) -> None:
    folder = runs_root / name
    folder.mkdir(parents=True)
    (folder / "notes.txt").write_text("not a local backtest artifact\n", encoding="utf-8")


def write_csv(path, fieldnames: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)
