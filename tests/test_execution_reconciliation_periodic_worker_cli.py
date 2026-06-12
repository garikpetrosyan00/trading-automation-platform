import json
from contextlib import contextmanager
from io import StringIO

import pytest
from pydantic import ValidationError

from app.cli import run_execution_reconciliation_worker as cli
from app.core.config import Settings
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_worker_status import ExecutionReconciliationWorkerStatusRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.binance import BinanceOrderHttpResponse, BinanceTestnetOrderClient, BinanceTestnetOrderQueryClientError
from app.services.execution_reconciliation_worker import (
    AutomaticReconciliationBatchSummary,
    AutomaticReconciliationJobResult,
)
from app.services.execution_reconciliation_worker_status import ExecutionReconciliationWorkerStatusService
from tests.test_execution_reconciliation_jobs import NOW, add_job, job_repository, worker_service


def test_periodic_worker_is_disabled_by_default() -> None:
    assert Settings(_env_file=None).binance_testnet_reconciliation_worker_enabled is False
    assert Settings(_env_file=None).binance_testnet_reconciliation_worker_poll_interval_seconds == 30
    assert Settings(_env_file=None).binance_testnet_reconciliation_worker_heartbeat_stale_after_seconds == 120


def test_periodic_worker_disabled_exits_without_processing_or_binance_query(monkeypatch) -> None:
    calls = []
    stdout = StringIO()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Disabled periodic worker must not call Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)

    exit_code = cli.main(
        [],
        worker_factory=fake_worker_factory(calls),
        heartbeat_service_factory=failing_heartbeat_factory(),
        settings_provider=lambda: worker_settings(enabled=False),
        stdout=stdout,
        stderr=StringIO(),
        install_signal_handlers=False,
    )

    assert exit_code == 0
    assert calls == []
    assert json.loads(stdout.getvalue()) == {"event": "worker_disabled", "worker_enabled": False}


def test_periodic_worker_enabled_calls_single_job_path_once_per_cycle() -> None:
    calls = []
    heartbeat_calls = []
    sleeps = []
    stop_controller = cli.StopController()

    def sleep_once(seconds):
        sleeps.append(seconds)
        stop_controller.request_stop()

    stdout = StringIO()
    exit_code = cli.run_loop(
        settings=worker_settings(enabled=True, poll_interval=7),
        worker_factory=fake_worker_factory(calls),
        heartbeat_service_factory=fake_heartbeat_factory(heartbeat_calls),
        sleep=sleep_once,
        stdout=stdout,
        stop_controller=stop_controller,
    )

    assert exit_code == 0
    assert calls == ["process_due_job"]
    assert heartbeat_calls == [
        "mark_worker_started",
        "mark_cycle_started",
        "mark_cycle_completed:found:1",
        "mark_worker_stopped",
    ]
    assert sleeps == [7]
    lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [line["event"] for line in lines] == ["worker_started", "worker_cycle_completed", "worker_stopped"]
    assert lines[1]["claimed_count"] == 1


def test_periodic_worker_multiple_due_jobs_are_not_batch_drained_in_one_cycle(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    first_job = add_job(db_session, bot.id, NOW)
    second_job = add_job(db_session, bot.id, NOW)
    stop_controller = cli.StopController()

    def stop_after_sleep(seconds):
        stop_controller.request_stop()

    def query_found(self, params):
        return BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 123,
                "clientOrderId": params["origClientOrderId"],
                "status": "FILLED",
            },
        )

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_found)

    cli.run_loop(
        settings=worker_settings(enabled=True),
        worker_factory=real_worker_factory(db_session),
        heartbeat_service_factory=real_heartbeat_factory(db_session),
        sleep=stop_after_sleep,
        stdout=StringIO(),
        stop_controller=stop_controller,
    )

    db_session.expire_all()
    assert job_repository(db_session).get_by_id(first_job.id).state == "resolved"
    assert job_repository(db_session).get_by_id(second_job.id).state == "pending"


def test_periodic_worker_rejects_invalid_poll_interval_configuration() -> None:
    with pytest.raises(ValidationError):
        worker_settings(enabled=True, poll_interval=0)
    with pytest.raises(ValidationError):
        worker_settings(enabled=True, poll_interval=3601)


def test_periodic_worker_sigterm_style_stop_is_graceful() -> None:
    calls = []
    stop_controller = cli.StopController()

    def request_sigterm(seconds):
        stop_controller.request_stop()

    stdout = StringIO()
    exit_code = cli.run_loop(
        settings=worker_settings(enabled=True),
        worker_factory=fake_worker_factory(calls),
        heartbeat_service_factory=fake_heartbeat_factory([]),
        sleep=request_sigterm,
        stdout=stdout,
        stop_controller=stop_controller,
    )

    assert exit_code == 0
    assert calls == ["process_due_job"]
    assert json.loads(stdout.getvalue().splitlines()[-1])["event"] == "worker_stopped"


def test_periodic_worker_unexpected_cycle_exception_is_safe_and_continues_to_next_sleep() -> None:
    stdout = StringIO()
    sleeps = []
    stop_controller = cli.StopController()

    def sleep_once(seconds):
        sleeps.append(seconds)
        stop_controller.request_stop()

    exit_code = cli.run_loop(
        settings=worker_settings(enabled=True, poll_interval=9),
        worker_factory=failing_worker_factory("unsafe-api-secret signature raw Binance payload headers"),
        heartbeat_service_factory=fake_heartbeat_factory([]),
        sleep=sleep_once,
        stdout=stdout,
        stop_controller=stop_controller,
    )

    assert exit_code == 0
    assert sleeps == [9]
    output = stdout.getvalue()
    assert "worker_cycle_failed" in output
    assert "unsafe-api-secret" not in output
    assert "signature" not in output
    assert "headers" not in output
    assert "raw Binance payload" not in output


def test_periodic_worker_found_mocked_binance_response_resolves_one_job(
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

    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "resolved"
    assert updated_attempt.metadata_["submission_recovered"] is True
    assert updated_attempt.metadata_["reconciliation_resolution"] == "found"


def test_periodic_worker_early_not_found_remains_safely_rescheduled(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)

    def query_not_found(self, params):
        return BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER raw payload"})

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_not_found)
    stdout = run_one_cycle(db_session)

    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "pending"
    assert updated_job.automatic_attempt_count == 1
    assert updated_attempt.metadata_["submission_recovered"] is False
    assert "NO_SUCH_ORDER" not in str(updated_attempt.metadata_)
    assert "not_found" in stdout.getvalue()


def test_periodic_worker_transient_network_failure_remains_safely_rescheduled(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)

    def query_timeout(self, params):
        raise BinanceTestnetOrderQueryClientError("raw signed URL timed out", trigger="timeout")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_timeout)
    stdout = run_one_cycle(db_session)

    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "pending"
    assert updated_job.last_failure_category == "timeout"
    assert "raw signed URL" not in str(updated_attempt.metadata_)
    assert "timeout" in stdout.getvalue()


def test_periodic_worker_output_contains_no_sensitive_request_data() -> None:
    unsafe_values = [
        "unsafe-api-key",
        "unsafe-api-secret",
        "signature",
        "X-MBX-APIKEY",
        "headers",
        "signed_params",
        "raw signed params",
        "credential",
    ]
    stdout = StringIO()
    stop_controller = cli.StopController()

    def stop_after_sleep(seconds):
        stop_controller.request_stop()

    cli.run_loop(
        settings=worker_settings(enabled=True),
        worker_factory=fake_worker_factory(
            [],
            summary=AutomaticReconciliationBatchSummary(
                claimed_count=1,
                processed_count=1,
                resolved_count=0,
                retried_count=1,
                exhausted_count=0,
                stale_count=0,
                results=[
                    AutomaticReconciliationJobResult(
                        job_id=1,
                        execution_attempt_id=2,
                        outcome="retried",
                        resolution="failed",
                        failure_category=" ".join(unsafe_values),
                        automatic_attempt_count=1,
                    )
                ],
            ),
        ),
        heartbeat_service_factory=fake_heartbeat_factory([]),
        sleep=stop_after_sleep,
        stdout=stdout,
        stop_controller=stop_controller,
    )

    output = stdout.getvalue()
    assert '"failure_category": "other"' in output
    for value in unsafe_values:
        assert value not in output


def test_periodic_worker_does_not_mutate_paper_portfolio_state(
    db_session,
    bot_stack_factory,
    funded_account,
    monkeypatch,
) -> None:
    funded_account(db_session)
    repository = PortfolioRepository(db_session)
    account_before = repository.get_account().cash_balance
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    add_job(db_session, bot.id, NOW)

    def query_found(self, params):
        return BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 222,
                "clientOrderId": params["origClientOrderId"],
                "status": "FILLED",
            },
        )

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_found)
    run_one_cycle(db_session)

    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_account().cash_balance == account_before


def run_one_cycle(db_session) -> StringIO:
    stdout = StringIO()
    stop_controller = cli.StopController()

    def stop_after_sleep(seconds):
        stop_controller.request_stop()

    cli.run_loop(
        settings=worker_settings(enabled=True),
        worker_factory=real_worker_factory(db_session),
        heartbeat_service_factory=real_heartbeat_factory(db_session),
        sleep=stop_after_sleep,
        stdout=stdout,
        stop_controller=stop_controller,
    )
    return stdout


def worker_settings(*, enabled: bool, poll_interval: int = 30) -> Settings:
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
        BINANCE_TESTNET_RECONCILIATION_WORKER_POLL_INTERVAL_SECONDS=poll_interval,
        BINANCE_TESTNET_RECONCILIATION_WORKER_HEARTBEAT_STALE_AFTER_SECONDS=120,
    )


def real_worker_factory(db_session):
    @contextmanager
    def factory():
        yield worker_service(
            db_session,
            now=NOW,
            settings=worker_settings(enabled=True),
        )

    return factory


def fake_worker_factory(calls: list[str], *, summary: AutomaticReconciliationBatchSummary | None = None):
    class FakeWorker:
        def process_due_job(self):
            calls.append("process_due_job")
            return summary or AutomaticReconciliationBatchSummary(
                claimed_count=1,
                processed_count=1,
                resolved_count=1,
                retried_count=0,
                exhausted_count=0,
                stale_count=0,
                results=[
                    AutomaticReconciliationJobResult(
                        job_id=1,
                        execution_attempt_id=2,
                        outcome="resolved",
                        resolution="found",
                        automatic_attempt_count=1,
                    )
                ],
            )

        def process_due_batch(self, *, limit=None):
            raise AssertionError("Periodic worker must call process_due_job, not process_due_batch")

    @contextmanager
    def factory():
        yield FakeWorker()

    return factory


def failing_worker_factory(message: str):
    class FailingWorker:
        def process_due_job(self):
            raise RuntimeError(message)

    @contextmanager
    def factory():
        yield FailingWorker()

    return factory


def real_heartbeat_factory(db_session):
    @contextmanager
    def factory(settings):
        yield ExecutionReconciliationWorkerStatusService(
            ExecutionReconciliationWorkerStatusRepository(db_session),
            settings=settings,
        )

    return factory


def fake_heartbeat_factory(calls: list[str]):
    class FakeHeartbeatService:
        def mark_worker_started(self):
            calls.append("mark_worker_started")

        def mark_cycle_started(self):
            calls.append("mark_cycle_started")

        def mark_cycle_completed(self, *, result_code, processed_reconciliation_job_id=None):
            calls.append(f"mark_cycle_completed:{result_code}:{processed_reconciliation_job_id}")

        def mark_cycle_failed(self):
            calls.append("mark_cycle_failed")

        def mark_worker_stopped(self):
            calls.append("mark_worker_stopped")

    @contextmanager
    def factory(settings):
        yield FakeHeartbeatService()

    return factory


def failing_heartbeat_factory():
    @contextmanager
    def factory(settings):
        raise AssertionError("Disabled periodic worker must not create heartbeat state")
        yield

    return factory
