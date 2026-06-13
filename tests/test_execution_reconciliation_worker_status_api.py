from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from io import StringIO

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.cli import run_execution_reconciliation_worker as worker_cli
from app.core.config import Settings
from app.main import app
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_worker_status import ExecutionReconciliationWorkerStatusRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.binance import BinanceOrderHttpResponse, BinanceTestnetOrderClient, BinanceTestnetOrderQueryClientError
from app.services.execution_reconciliation_worker_status import (
    BINANCE_TESTNET_RECONCILIATION_WORKER_NAME,
    ExecutionReconciliationWorkerStatusService,
)
from tests.test_execution_reconciliation_jobs import NOW, add_job, job_repository, worker_service
from tests.test_execution_reconciliation_periodic_worker_cli import failing_worker_factory


WORKER_STATUS_FIELDS = {
    "worker_name",
    "initialized",
    "configured_enabled",
    "state",
    "last_started_at",
    "last_heartbeat_at",
    "last_stopped_at",
    "last_cycle_started_at",
    "last_cycle_finished_at",
    "last_cycle_result_code",
    "last_processed_reconciliation_job_id",
    "heartbeat_stale_after_seconds",
    "is_stale",
    "pending_reconciliation_job_count",
    "claimed_reconciliation_job_count",
    "resolved_reconciliation_job_count",
    "exhausted_reconciliation_job_count",
    "expired_lease_count",
    "next_due_reconciliation_job_at",
    "updated_at",
}


def test_reconciliation_worker_status_model_schema(db_session) -> None:
    inspector = inspect(db_session.bind)

    assert "execution_reconciliation_worker_status" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("execution_reconciliation_worker_status")}
    assert {
        "id",
        "worker_name",
        "state",
        "last_started_at",
        "last_heartbeat_at",
        "last_stopped_at",
        "last_cycle_started_at",
        "last_cycle_finished_at",
        "last_cycle_result_code",
        "last_processed_reconciliation_job_id",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_worker_status_no_heartbeat_row_returns_initialized_false(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-reconciliation-worker/status")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "worker_name": BINANCE_TESTNET_RECONCILIATION_WORKER_NAME,
        "initialized": False,
        "configured_enabled": False,
        "state": None,
        "last_started_at": None,
        "last_heartbeat_at": None,
        "last_stopped_at": None,
        "last_cycle_started_at": None,
        "last_cycle_finished_at": None,
        "last_cycle_result_code": None,
        "last_processed_reconciliation_job_id": None,
        "heartbeat_stale_after_seconds": 120,
        "is_stale": False,
        "pending_reconciliation_job_count": 0,
        "claimed_reconciliation_job_count": 0,
        "resolved_reconciliation_job_count": 0,
        "exhausted_reconciliation_job_count": 0,
        "expired_lease_count": 0,
        "next_due_reconciliation_job_at": None,
        "updated_at": None,
    }


def test_worker_status_response_reports_pending_jobs_and_next_due_time(
    db_session,
    bot_stack_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    first = add_job(db_session, bot.id, NOW + timedelta(minutes=5))
    add_job(db_session, bot.id, NOW + timedelta(minutes=10))
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-reconciliation-worker/status")

    assert response.status_code == 200
    body = response.json()
    assert body["pending_reconciliation_job_count"] == 2
    assert body["claimed_reconciliation_job_count"] == 0
    assert body["resolved_reconciliation_job_count"] == 0
    assert body["exhausted_reconciliation_job_count"] == 0
    assert body["expired_lease_count"] == 0
    assert body["next_due_reconciliation_job_at"] == first.next_attempt_at.isoformat()


def test_worker_status_response_reports_claimed_and_expired_jobs(
    db_session,
    bot_stack_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    active = add_job(db_session, bot.id, NOW - timedelta(minutes=2))
    expired = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    active_claim, expired_claim = job_repository(db_session).claim_due_jobs(
        now=NOW,
        lease_seconds=60,
        limit=2,
    )
    active_job = job_repository(db_session).get_by_id(active.id)
    active_job.lease_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    expired_job = job_repository(db_session).get_by_id(expired.id)
    expired_job.lease_expires_at = NOW - timedelta(seconds=1)
    db_session.add(active_job)
    db_session.add(expired_job)
    db_session.commit()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-reconciliation-worker/status")

    assert response.status_code == 200
    body = response.json()
    assert body["pending_reconciliation_job_count"] == 0
    assert body["claimed_reconciliation_job_count"] == 2
    assert body["expired_lease_count"] == 1
    assert body["next_due_reconciliation_job_at"] is None
    assert active_claim.lease_token not in response.text
    assert expired_claim.lease_token not in response.text


def test_worker_status_response_reports_resolved_and_exhausted_jobs(
    db_session,
    bot_stack_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    resolved = add_job(db_session, bot.id, NOW - timedelta(minutes=2))
    exhausted = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    claims = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=2)
    claims_by_id = {claim.id: claim for claim in claims}
    job_repository(db_session).mark_claimed_job_resolved(
        job_id=resolved.id,
        lease_token=claims_by_id[resolved.id].lease_token,
        checked_at=NOW,
        resolution="found",
    )
    job_repository(db_session).mark_claimed_job_exhausted(
        job_id=exhausted.id,
        lease_token=claims_by_id[exhausted.id].lease_token,
        checked_at=NOW,
        resolution="not_found",
        failure_category=None,
    )
    db_session.commit()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-reconciliation-worker/status")

    assert response.status_code == 200
    body = response.json()
    assert body["pending_reconciliation_job_count"] == 0
    assert body["claimed_reconciliation_job_count"] == 0
    assert body["resolved_reconciliation_job_count"] == 1
    assert body["exhausted_reconciliation_job_count"] == 1
    assert body["expired_lease_count"] == 0
    assert body["next_due_reconciliation_job_at"] is None


def test_disabled_periodic_worker_does_not_create_heartbeat_state(db_session) -> None:
    exit_code = worker_cli.main(
        [],
        worker_factory=failing_worker_factory("must not run"),
        heartbeat_service_factory=real_heartbeat_factory(db_session),
        settings_provider=lambda: worker_settings(enabled=False),
        stdout=StringIO(),
        stderr=StringIO(),
        install_signal_handlers=False,
    )

    assert exit_code == 0
    assert status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME) is None


def test_enabled_worker_records_started_and_normal_no_due_cycle(db_session) -> None:
    run_one_cycle(db_session)

    status = status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME)
    assert status is not None
    assert status.state == "stopped"
    assert status.last_started_at is not None
    assert status.last_heartbeat_at is not None
    assert status.last_stopped_at is not None
    assert status.last_cycle_started_at is not None
    assert status.last_cycle_finished_at is not None
    assert status.last_cycle_result_code == "no_due_job"
    assert status.last_processed_reconciliation_job_id is None


def test_found_order_cycle_records_safe_completed_result(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)

    def query_found(self, params):
        return BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 555,
                "clientOrderId": params["origClientOrderId"],
                "status": "NEW",
            },
        )

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_found)
    run_one_cycle(db_session)

    status = status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME)
    assert status.last_cycle_result_code == "found"
    assert status.last_processed_reconciliation_job_id == job.id


def test_not_found_retry_cycle_records_safe_result_without_changing_retry_semantics(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)

    def query_not_found(self, params):
        return BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER raw payload"})

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_not_found)
    run_one_cycle(db_session)

    db_session.expire_all()
    status = status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME)
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert status.last_cycle_result_code == "not_found"
    assert status.last_processed_reconciliation_job_id == job.id
    assert updated_job.state == "pending"
    assert updated_job.automatic_attempt_count == 1
    assert updated_attempt.metadata_["submission_recovered"] is False


def test_transient_network_failure_records_safe_result_without_raw_exception(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)

    def query_timeout(self, params):
        raise BinanceTestnetOrderQueryClientError("unsafe raw signed URL timed out", trigger="timeout")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_timeout)
    run_one_cycle(db_session)

    status = status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME)
    assert status.last_cycle_result_code == "timeout"
    assert status.last_processed_reconciliation_job_id == job.id
    assert "unsafe raw signed URL" not in str(status.__dict__)


def test_unexpected_cycle_exception_stores_only_generic_safe_result(db_session) -> None:
    run_one_cycle(
        db_session,
        worker_factory=failing_worker_factory("unsafe-api-secret signature raw traceback headers"),
    )

    status = status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME)
    assert status.last_cycle_result_code == "worker_cycle_failed"
    assert status.last_processed_reconciliation_job_id is None
    serialized = str(status.__dict__)
    assert "unsafe-api-secret" not in serialized
    assert "signature" not in serialized
    assert "traceback" not in serialized
    assert "headers" not in serialized


def test_graceful_stop_records_stopped_state(db_session) -> None:
    run_one_cycle(db_session)

    status = status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME)
    assert status.state == "stopped"
    assert status.last_stopped_at is not None


def test_worker_status_recent_and_old_heartbeat_staleness(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    status_service(db_session, now=NOW).mark_worker_started()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        recent_response = client.get("/api/v1/execution-reconciliation-worker/status")

    assert recent_response.status_code == 200
    assert recent_response.json()["initialized"] is True
    assert recent_response.json()["is_stale"] is True

    status = status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME)
    status.last_heartbeat_at = datetime.now(timezone.utc)
    db_session.add(status)
    db_session.commit()

    with TestClient(app) as client:
        fresh_response = client.get("/api/v1/execution-reconciliation-worker/status")

    assert fresh_response.status_code == 200
    assert fresh_response.json()["is_stale"] is False


def test_worker_status_endpoint_exposes_only_allowlisted_safe_fields(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    service = status_service(db_session)
    service.mark_worker_started()
    status = status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME)
    status.last_cycle_result_code = "unsafe-api-secret signature raw payload headers"
    db_session.add(status)
    db_session.commit()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-reconciliation-worker/status")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == WORKER_STATUS_FIELDS
    assert body["last_cycle_result_code"] == "other"
    serialized = response.text
    for unsafe in ("unsafe-api-secret", "signature", "raw payload", "headers", "lease_token", "metadata"):
        assert unsafe not in serialized


def test_worker_status_endpoint_is_read_only_and_does_not_mutate_portfolio_or_query_binance(
    db_session,
    funded_account,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    funded_account(db_session)
    portfolio_repository = PortfolioRepository(db_session)
    account_before = portfolio_repository.get_account().cash_balance
    orders_before = portfolio_repository.list_orders()
    fills_before = portfolio_repository.list_fills()
    status_service(db_session).mark_worker_started()
    before = status_snapshot(status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Worker status endpoint must not query Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)
    monkeypatch.setattr(BinanceTestnetOrderClient, "submit_signed_market_order", fail_if_called)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-reconciliation-worker/status")

    assert response.status_code == 200
    db_session.expire_all()
    after = status_snapshot(status_repository(db_session).get_by_worker_name(BINANCE_TESTNET_RECONCILIATION_WORKER_NAME))
    assert after == before
    assert portfolio_repository.list_orders() == orders_before
    assert portfolio_repository.list_fills() == fills_before
    assert portfolio_repository.get_account().cash_balance == account_before


def run_one_cycle(db_session, *, worker_factory=None) -> StringIO:
    stdout = StringIO()
    stop_controller = worker_cli.StopController()

    def stop_after_sleep(seconds):
        stop_controller.request_stop()

    worker_cli.run_loop(
        settings=worker_settings(enabled=True),
        worker_factory=worker_factory or real_worker_factory(db_session),
        heartbeat_service_factory=real_heartbeat_factory(db_session),
        sleep=stop_after_sleep,
        stdout=stdout,
        stop_controller=stop_controller,
    )
    return stdout


def real_worker_factory(db_session):
    @contextmanager
    def factory():
        yield worker_service(db_session, now=NOW, settings=worker_settings(enabled=True))

    return factory


def real_heartbeat_factory(db_session):
    @contextmanager
    def factory(settings):
        yield status_service(db_session, settings=settings)

    return factory


def status_service(db_session, *, settings=None, now=None) -> ExecutionReconciliationWorkerStatusService:
    return ExecutionReconciliationWorkerStatusService(
        ExecutionReconciliationWorkerStatusRepository(db_session),
        settings=settings or worker_settings(enabled=True),
        now_provider=(lambda: now) if now is not None else None,
    )


def status_repository(db_session) -> ExecutionReconciliationWorkerStatusRepository:
    return ExecutionReconciliationWorkerStatusRepository(db_session)


def status_snapshot(status) -> dict:
    return {
        "state": status.state,
        "last_started_at": status.last_started_at,
        "last_heartbeat_at": status.last_heartbeat_at,
        "last_stopped_at": status.last_stopped_at,
        "last_cycle_started_at": status.last_cycle_started_at,
        "last_cycle_finished_at": status.last_cycle_finished_at,
        "last_cycle_result_code": status.last_cycle_result_code,
        "last_processed_reconciliation_job_id": status.last_processed_reconciliation_job_id,
        "updated_at": status.updated_at,
    }


def worker_settings(*, enabled: bool) -> Settings:
    return Settings(
        _env_file=None,
        BINANCE_TESTNET_BROKER_ENABLED=True,
        BINANCE_TESTNET_ORDER_SUBMISSION_ENABLED=True,
        BINANCE_TESTNET_BASE_URL="https://testnet.binance.vision",
        BINANCE_TESTNET_API_KEY="test-api-key",
        BINANCE_TESTNET_API_SECRET="test-api-secret",
        BINANCE_TESTNET_RECV_WINDOW=5000,
        BINANCE_TESTNET_TIMEOUT_SECONDS=5,
        BINANCE_TESTNET_RECONCILIATION_INITIAL_DELAY_SECONDS=300,
        BINANCE_TESTNET_RECONCILIATION_LEASE_SECONDS=30,
        BINANCE_TESTNET_RECONCILIATION_RETRY_DELAY_SECONDS=60,
        BINANCE_TESTNET_RECONCILIATION_MAX_AUTOMATIC_ATTEMPTS=5,
        BINANCE_TESTNET_RECONCILIATION_BATCH_SIZE=10,
        BINANCE_TESTNET_RECONCILIATION_WORKER_ENABLED=enabled,
        BINANCE_TESTNET_RECONCILIATION_WORKER_POLL_INTERVAL_SECONDS=30,
        BINANCE_TESTNET_RECONCILIATION_WORKER_HEARTBEAT_STALE_AFTER_SECONDS=120,
    )
