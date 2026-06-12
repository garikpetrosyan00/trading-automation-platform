import json
import subprocess
import sys
from contextlib import contextmanager
from io import StringIO

from app.cli import process_execution_reconciliation_job as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.binance import BinanceOrderHttpResponse, BinanceTestnetOrderClient, BinanceTestnetOrderQueryClientError
from app.services.execution_reconciliation_worker import (
    AutomaticReconciliationBatchSummary,
    AutomaticReconciliationJobResult,
)
from tests.test_execution_reconciliation_jobs import NOW, add_job, job_repository, worker_service, worker_settings


def test_one_shot_cli_module_import_does_not_initialize_db_session_module() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import app.cli.process_execution_reconciliation_job; "
            "print('app.db.session' in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_one_shot_cli_no_due_job_exits_safely_and_does_not_query_binance(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    future_job = add_job(db_session, bot.id, NOW.replace(hour=13))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("No due one-shot reconciliation job must not query Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cli.main(
        [],
        worker_factory=real_worker_factory(db_session),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue()) == {
        "claimed_count": 0,
        "due_job_found": False,
        "exhausted_count": 0,
        "processed": False,
        "processed_count": 0,
        "resolved_count": 0,
        "results": [],
        "retried_count": 0,
        "stale_count": 0,
    }
    db_session.expire_all()
    assert job_repository(db_session).get_by_id(future_job.id).state == "pending"


def test_one_shot_cli_invokes_single_job_worker_path_only_once() -> None:
    calls = []
    stdout = StringIO()

    exit_code = cli.main(
        [],
        worker_factory=fake_worker_factory(calls),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert calls == ["process_due_job"]
    assert json.loads(stdout.getvalue())["claimed_count"] == 1


def test_one_shot_cli_processes_at_most_one_due_job_when_multiple_are_due(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    first_job = add_job(db_session, bot.id, NOW)
    second_job = add_job(db_session, bot.id, NOW)
    query_calls = []

    def query_found(self, params):
        query_calls.append(params)
        return BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 321,
                "clientOrderId": params["origClientOrderId"],
                "status": "FILLED",
            },
        )

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_found)

    exit_code = cli.main([], worker_factory=real_worker_factory(db_session), stdout=StringIO(), stderr=StringIO())

    assert exit_code == 0
    assert len(query_calls) == 1
    db_session.expire_all()
    assert job_repository(db_session).get_by_id(first_job.id).state == "resolved"
    assert job_repository(db_session).get_by_id(second_job.id).state == "pending"


def test_one_shot_cli_found_mocked_binance_response_resolves_job(
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
                "orderId": 999,
                "clientOrderId": params["origClientOrderId"],
                "status": "NEW",
            },
        )

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_found)
    stdout = StringIO()

    exit_code = cli.main([], worker_factory=real_worker_factory(db_session), stdout=stdout, stderr=StringIO())

    assert exit_code == 0
    assert json.loads(stdout.getvalue())["results"][0]["outcome"] == "resolved"
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "resolved"
    assert updated_attempt.metadata_["submission_recovered"] is True
    assert updated_attempt.metadata_["reconciliation_resolution"] == "found"


def test_one_shot_cli_early_not_found_remains_safely_rescheduled(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)

    def query_not_found(self, params):
        return BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER raw payload"})

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_not_found)
    stdout = StringIO()

    exit_code = cli.main(
        [],
        worker_factory=real_worker_factory(db_session, settings=worker_settings(max_attempts=3, retry_delay=45)),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    body = json.loads(stdout.getvalue())
    assert body["retried_count"] == 1
    assert body["results"][0]["resolution"] == "not_found"
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "pending"
    assert updated_job.automatic_attempt_count == 1
    assert updated_attempt.final_reason == "testnet_order_reconciliation_unresolved"
    assert updated_attempt.metadata_["submission_recovered"] is False
    assert "NO_SUCH_ORDER" not in str(updated_attempt.metadata_)


def test_one_shot_cli_transient_network_failure_remains_safely_rescheduled(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)

    def query_timeout(self, params):
        raise BinanceTestnetOrderQueryClientError("raw signed URL timed out", trigger="timeout")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_timeout)
    stdout = StringIO()

    exit_code = cli.main(
        [],
        worker_factory=real_worker_factory(db_session, settings=worker_settings(max_attempts=3, retry_delay=45)),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    body = json.loads(stdout.getvalue())
    assert body["retried_count"] == 1
    assert body["results"][0]["failure_category"] == "timeout"
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "pending"
    assert updated_job.last_failure_category == "timeout"
    assert "raw signed URL" not in str(updated_attempt.metadata_)


def test_one_shot_cli_stdout_contains_no_sensitive_request_data() -> None:
    unsafe_values = [
        "unsafe-api-key",
        "unsafe-api-secret",
        "signature",
        "symbol=BTCUSDT&signature=unsafe",
        "X-MBX-APIKEY",
        "NO_SUCH_ORDER raw payload",
        "headers",
        "signed_params",
    ]
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cli.main(
        [],
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
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    body = json.loads(stdout.getvalue())
    assert body["results"][0]["failure_category"] == "other"
    serialized = stdout.getvalue() + stderr.getvalue()
    for value in unsafe_values:
        assert value not in serialized


def test_one_shot_cli_does_not_mutate_paper_portfolio_state(
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

    exit_code = cli.main([], worker_factory=real_worker_factory(db_session), stdout=StringIO(), stderr=StringIO())

    assert exit_code == 0
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_account().cash_balance == account_before


def test_one_shot_cli_unexpected_failure_returns_safe_error() -> None:
    stderr = StringIO()

    exit_code = cli.main(
        [],
        worker_factory=failing_worker_factory("unsafe-api-secret signature raw Binance payload"),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 1
    assert stderr.getvalue().strip() == "error: execution reconciliation job command failed"
    assert "unsafe-api-secret" not in stderr.getvalue()
    assert "signature" not in stderr.getvalue()


def real_worker_factory(db_session, *, settings=None):
    @contextmanager
    def factory():
        yield worker_service(
            db_session,
            now=NOW,
            settings=settings or worker_settings(batch_size=10),
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
            raise AssertionError("One-shot CLI must call process_due_job")

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
