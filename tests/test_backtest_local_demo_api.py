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


def test_local_demo_api_lists_sweeps_sorted_and_sanitized(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_sweep_artifacts(runs_root, "z_sweep", symbol="ETHUSDT")
    write_sweep_artifacts(runs_root, "a_sweep")
    write_incomplete_folder(runs_root, "not_a_sweep")
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/sweeps")
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "name": "a_sweep",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "combinations_count": 2,
                "best_result": sweep_best_result(),
                "artifacts": {
                    "sweep_summary_json": True,
                    "sweep_results_csv": True,
                    "sweep_report_md": True,
                },
            },
            {
                "name": "z_sweep",
                "symbol": "ETHUSDT",
                "timeframe": "1h",
                "combinations_count": 2,
                "best_result": sweep_best_result(),
                "artifacts": {
                    "sweep_summary_json": True,
                    "sweep_results_csv": True,
                    "sweep_report_md": True,
                },
            },
        ]
    }
    assert str(tmp_path.resolve()) not in response.text


def test_local_demo_api_reads_sweep_summary_results_and_report(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_sweep_artifacts(runs_root, "demo_sweep")
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            summary_response = client.get("/api/v1/backtests/local-demo/sweeps/demo_sweep/summary")
            results_response = client.get("/api/v1/backtests/local-demo/sweeps/demo_sweep/results")
            report_response = client.get("/api/v1/backtests/local-demo/sweeps/demo_sweep/report")
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert summary_response.status_code == 200
    assert summary_response.json() == {
        "sweep_name": "demo_sweep",
        "artifact": "sweep_summary",
        "summary": {
            "result": "PASS",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "strategy_type": "price_threshold",
            "initial_balance": "10000",
            "fee_rate": "0.001",
            "order_quantity": "0.01",
            "combinations_count": 2,
            "ranking_metric": "final_equity",
            "profitability_note": "Historical local simulation only; not a profitability guarantee.",
            "best_result": sweep_best_result(),
        },
    }
    assert str(tmp_path.resolve()) not in summary_response.text

    assert results_response.status_code == 200
    assert results_response.json() == {
        "sweep_name": "demo_sweep",
        "artifact": "sweep_results",
        "items": [
            sweep_best_result(),
            {
                "rank": 2,
                "run_name": "run_001_entry_90000_exit_105000",
                "entry_below": "90000",
                "exit_above": "105000",
                "final_equity": "10010",
                "total_return_pct": "0.1",
                "trades_count": 2,
                "win_rate_pct": "50",
                "max_drawdown_pct": "0.5",
                "fees_paid": "1",
            },
        ],
    }
    assert str(tmp_path.resolve()) not in results_response.text

    assert report_response.status_code == 200
    assert report_response.headers["content-type"].startswith("text/markdown")
    assert "# Sweep Report" in report_response.text
    assert str(tmp_path.resolve()) not in report_response.text


def test_local_demo_api_compares_two_saved_runs(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_comparison_run(
        runs_root,
        "base",
        {
            "strategy_type": "price_threshold",
            "entry_below": "90000",
            "exit_above": "105000",
            "starting_balance": "10000",
            "ending_balance": "10010",
            "total_return": "10",
            "max_drawdown_pct": "1.5",
        },
    )
    write_comparison_run(
        runs_root,
        "candidate",
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
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/backtests/local-demo/runs/compare",
                json={"runs": [{"name": "base"}, {"path": str((runs_root / "candidate").resolve())}]},
            )
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "PASS"
    assert body["runs_count"] == 2
    assert body["ranking_metrics"] == ["overall_score", "total_return", "ending_balance", "max_drawdown_pct"]
    assert [item["run_name"] for item in body["rankings"]["overall_score"]] == ["candidate", "base"]
    assert [item["run_name"] for item in body["rankings"]["total_return"]] == ["candidate", "base"]
    assert [item["run_name"] for item in body["rankings"]["ending_balance"]] == ["candidate", "base"]
    assert [item["run_name"] for item in body["rankings"]["max_drawdown_pct"]] == ["candidate", "base"]
    candidate = next(item for item in body["runs"] if item["run_name"] == "candidate")
    assert candidate["run_path"] == "candidate"
    assert candidate["summary"]["strategy_type"] == "moving_average_crossover"
    assert candidate["summary"]["fast_window"] == "2"
    assert candidate["overall_score"] == candidate["summary"]["overall_score"]
    assert "score_components" in candidate
    assert "score_warnings" in candidate
    assert body["recommendation"]["recommended_run"]["run_name"] == "candidate"
    assert body["recommendation"]["recommended_run"]["run_path"] == "candidate"
    assert "run_dir" not in body["recommendation"]["recommended_run"]
    assert body["recommendation"]["recommendation_status"] in {"weak_recommendation", "not_recommended"}
    assert str(tmp_path.resolve()) not in response.text


def test_local_demo_api_compares_three_runs_with_deterministic_ranking(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_comparison_run(
        runs_root,
        "z_run",
        {"starting_balance": "10000", "ending_balance": "10050", "total_return": "50", "max_drawdown_pct": "1"},
    )
    write_comparison_run(
        runs_root,
        "a_run",
        {"starting_balance": "10000", "ending_balance": "10050", "total_return": "50", "max_drawdown_pct": "1"},
    )
    write_comparison_run(
        runs_root,
        "best_return",
        {"starting_balance": "10000", "ending_balance": "10100", "total_return": "100", "max_drawdown_pct": "3"},
    )
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/backtests/local-demo/runs/compare",
                json={"runs": [{"name": "z_run"}, {"name": "a_run"}, {"name": "best_return"}]},
            )
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["runs_count"] == 3
    assert [item["run_name"] for item in body["rankings"]["overall_score"]] == ["best_return", "a_run", "z_run"]
    assert [item["run_name"] for item in body["runs"]] == ["best_return", "a_run", "z_run"]
    assert [item["run_name"] for item in body["rankings"]["total_return"]] == ["best_return", "a_run", "z_run"]
    assert [item["run_name"] for item in body["rankings"]["ending_balance"]] == ["best_return", "a_run", "z_run"]
    assert [item["run_name"] for item in body["rankings"]["max_drawdown_pct"]] == ["a_run", "z_run", "best_return"]


def test_local_demo_api_compare_missing_run_returns_clean_404(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_comparison_run(runs_root, "existing", {"starting_balance": "10000", "ending_balance": "10010"})
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/backtests/local-demo/runs/compare",
                json={"runs": [{"name": "existing"}, {"name": "missing"}]},
            )
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 404
    assert response.json() == {"detail": "Local backtest artifact not found", "error_code": "artifact_not_found"}
    assert str(tmp_path.resolve()) not in response.text


def test_local_demo_api_compare_rejects_invalid_path(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_comparison_run(runs_root, "existing", {"starting_balance": "10000", "ending_balance": "10010"})
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/backtests/local-demo/runs/compare",
                json={"runs": [{"name": "existing"}, {"path": "../outside"}]},
            )
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid local backtest artifact path", "error_code": "invalid_artifact_path"}


def test_local_demo_api_compare_rejects_fewer_than_two_runs(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    override_local_artifact_service(tmp_path / "runs")

    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/backtests/local-demo/runs/compare", json={"runs": [{"name": "only"}]})
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 422
    assert response.json() == {"detail": "At least two local backtest runs are required", "error_code": "not_enough_runs"}


def test_local_demo_api_compare_derives_metrics_from_older_artifacts(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    runs_root = tmp_path / "runs"
    write_comparison_run(runs_root, "base", {"initial_balance": "10000"})
    candidate_dir = write_comparison_run(runs_root, "candidate", {"initial_balance": "10000"})
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
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/backtests/local-demo/runs/compare",
                json={"runs": [{"name": "base"}, {"path": "candidate"}]},
            )
    finally:
        app.dependency_overrides.pop(get_local_backtest_artifact_service, None)

    assert response.status_code == 200
    candidate = next(item for item in response.json()["runs"] if item["run_name"] == "candidate")
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


def test_local_demo_api_missing_sweep_artifact_returns_clean_404(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    override_local_artifact_service(tmp_path / "runs")

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/sweeps/missing/summary")
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


def test_local_demo_api_rejects_sweep_path_traversal(
    tmp_path,
    configure_app_state,
    stub_market_data_service,
    noop_bot_runner,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    override_local_artifact_service(tmp_path / "runs")

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/backtests/local-demo/sweeps/..secret/summary")
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
    write_comparison_run(runs_root, "demo_compare", {"initial_balance": "10000", "ending_balance": "10020"})
    write_bundle_artifacts(runs_root, "demo_bundle")
    write_sweep_artifacts(runs_root, "demo_sweep")
    override_local_artifact_service(runs_root)

    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/backtests/local-demo/runs").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/bundles").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/sweeps").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/runs/demo_001/summary").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/runs/demo_001/report").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/bundles/demo_bundle/manifest").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/sweeps/demo_sweep/summary").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/sweeps/demo_sweep/results").status_code == 200
            assert client.get("/api/v1/backtests/local-demo/sweeps/demo_sweep/report").status_code == 200
            assert (
                client.post(
                    "/api/v1/backtests/local-demo/runs/compare",
                    json={"runs": [{"name": "demo_001"}, {"name": "demo_compare"}]},
                ).status_code
                == 200
            )
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


def write_comparison_run(runs_root, run_name: str, summary: dict):
    run_dir = runs_root / run_name
    run_dir.mkdir(parents=True)
    payload = {
        "result": "PASS",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        **summary,
    }
    (run_dir / "summary.json").write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(
        run_dir / "trades.csv",
        ["timestamp", "side", "realized_pnl"],
        [
            ["2025-01-01T00:00:00Z", "buy", ""],
            ["2025-01-01T01:00:00Z", "sell", summary.get("realized_pnl", "10")],
        ],
    )
    write_csv(
        run_dir / "equity_curve.csv",
        ["timestamp", "equity"],
        [
            ["2025-01-01T00:00:00Z", summary.get("starting_balance", summary.get("initial_balance", "10000"))],
            ["2025-01-01T01:00:00Z", summary.get("ending_balance", summary.get("final_equity", "10010"))],
        ],
    )
    return run_dir


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


def write_sweep_artifacts(runs_root, sweep_name: str, *, symbol: str = "BTCUSDT") -> None:
    sweep_dir = runs_root / sweep_name
    sweep_dir.mkdir(parents=True)
    (sweep_dir / "sweep_summary.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "symbol": symbol,
                "timeframe": "1h",
                "strategy_type": "price_threshold",
                "initial_balance": "10000",
                "fee_rate": "0.001",
                "order_quantity": "0.01",
                "combinations_count": 2,
                "ranking_metric": "final_equity",
                "profitability_note": "Historical local simulation only; not a profitability guarantee.",
                "best_result": {
                    **sweep_best_result(),
                    "summary_path": str((sweep_dir / "run_002_entry_95000_exit_110000" / "summary.json").resolve()),
                },
                "results": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_csv(
        sweep_dir / "sweep_results.csv",
        [
            "rank",
            "run_name",
            "entry_below",
            "exit_above",
            "final_equity",
            "total_return_pct",
            "trades_count",
            "win_rate_pct",
            "max_drawdown_pct",
            "fees_paid",
            "summary_path",
        ],
        [
            [
                "1",
                "run_002_entry_95000_exit_110000",
                "95000",
                "110000",
                "10020",
                "0.2",
                "2",
                "100",
                "0",
                "1",
                str((sweep_dir / "run_002_entry_95000_exit_110000" / "summary.json").resolve()),
            ],
            [
                "2",
                "run_001_entry_90000_exit_105000",
                "90000",
                "105000",
                "10010",
                "0.1",
                "2",
                "50",
                "0.5",
                "1",
                str((sweep_dir / "run_001_entry_90000_exit_105000" / "summary.json").resolve()),
            ],
        ],
    )
    (sweep_dir / "sweep_report.md").write_text("# Sweep Report\n\nSource: " + str(sweep_dir.resolve()) + "\n", encoding="utf-8")


def sweep_best_result() -> dict:
    return {
        "rank": 1,
        "run_name": "run_002_entry_95000_exit_110000",
        "entry_below": "95000",
        "exit_above": "110000",
        "final_equity": "10020",
        "total_return_pct": "0.2",
        "trades_count": 2,
        "win_rate_pct": "100",
        "max_drawdown_pct": "0",
        "fees_paid": "1",
    }


def write_csv(path, fieldnames: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)
