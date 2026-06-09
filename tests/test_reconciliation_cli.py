import json
import subprocess
import sys
from contextlib import contextmanager
from io import StringIO
from types import SimpleNamespace

from app.cli import process_binance_testnet_reconciliation as cli
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.binance import BinanceTestnetOrderClient
from app.services.execution_reconciliation_worker import (
    AutomaticReconciliationBatchSummary,
    AutomaticReconciliationJobResult,
)


def test_cli_module_import_does_not_initialize_db_session_module() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import app.cli.process_binance_testnet_reconciliation; "
            "print('app.db.session' in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_cli_runs_exactly_one_worker_batch_with_configured_default_batch_size(monkeypatch) -> None:
    calls = []
    stdout = StringIO()
    stderr = StringIO()

    monkeypatch.setattr(BinanceTestnetOrderClient, "submit_signed_market_order", fail_if_called)

    exit_code = cli.main(
        [],
        worker_factory=fake_worker_factory(calls),
        settings_provider=lambda: settings(batch_size=7),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert calls == [7]
    body = json.loads(stdout.getvalue())
    assert body["claimed_count"] == 2
    assert body["retried_count"] == 1
    assert stderr.getvalue() == ""


def test_cli_batch_size_override_is_forwarded() -> None:
    calls = []
    stdout = StringIO()

    exit_code = cli.main(
        ["--batch-size", "3"],
        worker_factory=fake_worker_factory(calls),
        settings_provider=lambda: settings(batch_size=7),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert calls == [3]


def test_cli_help_does_not_construct_settings_or_worker_dependencies() -> None:
    calls = []

    def fail_settings():
        raise AssertionError("help must not read settings")

    exit_code = cli.main(
        ["--help"],
        worker_factory=fake_worker_factory(calls),
        settings_provider=fail_settings,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert calls == []


def test_cli_rejects_invalid_batch_sizes_without_running_worker() -> None:
    cases = [
        ["--batch-size", "0"],
        ["--batch-size", "-1"],
        ["--batch-size", "abc"],
        ["--batch-size", "101"],
    ]

    for argv in cases:
        calls = []
        stderr = StringIO()

        exit_code = cli.main(
            argv,
            worker_factory=fake_worker_factory(calls),
            settings_provider=lambda: settings(batch_size=7),
            stdout=StringIO(),
            stderr=stderr,
        )

        assert exit_code == 2
        assert calls == []
        assert "error:" in stderr.getvalue()


def test_cli_rejects_oversized_configured_batch_before_running_worker() -> None:
    calls = []
    stderr = StringIO()

    exit_code = cli.main(
        [],
        worker_factory=fake_worker_factory(calls),
        settings_provider=lambda: settings(batch_size=101),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 2
    assert calls == []
    assert stderr.getvalue().strip() == "error: batch size must be at most 100"


def test_cli_stdout_is_safe_json_aggregate_only() -> None:
    stdout = StringIO()
    stderr = StringIO()
    unsafe_values = [
        "unsafe-api-key",
        "unsafe-api-secret",
        "signature",
        "symbol=BTCUSDT&signature=unsafe",
        "X-MBX-APIKEY",
        "NO_SUCH_ORDER raw payload",
        "tap_client_order_id",
        "exchange_order_id_123",
        "lease_token",
    ]

    exit_code = cli.main(
        [],
        worker_factory=fake_worker_factory([], unsafe_failure_category=" ".join(unsafe_values)),
        settings_provider=lambda: settings(batch_size=5),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    body = json.loads(stdout.getvalue())
    assert set(body) == {
        "claimed_count",
        "processed_count",
        "resolved_count",
        "retried_count",
        "exhausted_count",
        "stale_count",
    }
    serialized = stdout.getvalue() + stderr.getvalue()
    for value in unsafe_values:
        assert value not in serialized


def test_cli_normal_worker_outcomes_return_zero() -> None:
    stdout = StringIO()

    exit_code = cli.main(
        [],
        worker_factory=fake_worker_factory(
            [],
            summary=AutomaticReconciliationBatchSummary(
                claimed_count=4,
                processed_count=4,
                resolved_count=1,
                retried_count=1,
                exhausted_count=1,
                stale_count=1,
                results=[],
            ),
        ),
        settings_provider=lambda: settings(batch_size=4),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {
        "claimed_count": 4,
        "processed_count": 4,
        "resolved_count": 1,
        "retried_count": 1,
        "exhausted_count": 1,
        "stale_count": 1,
    }


def test_cli_unexpected_failure_returns_safe_nonzero_error() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cli.main(
        [],
        worker_factory=failing_worker_factory("unsafe-api-secret signature raw Binance payload lease_token"),
        settings_provider=lambda: settings(batch_size=5),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue().strip() == "error: automatic reconciliation command failed"
    assert "unsafe-api-secret" not in stderr.getvalue()
    assert "signature" not in stderr.getvalue()
    assert "lease_token" not in stderr.getvalue()


def test_cli_does_not_mutate_paper_portfolio(db_session, funded_account) -> None:
    funded_account(db_session)
    repository = PortfolioRepository(db_session)
    account_before = repository.get_account().cash_balance

    exit_code = cli.main(
        [],
        worker_factory=fake_worker_factory([]),
        settings_provider=lambda: settings(batch_size=5),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_account().cash_balance == account_before


def test_default_worker_factory_closes_session(monkeypatch) -> None:
    closed = []

    class FakeSession:
        def close(self):
            closed.append(True)

    import app.db.session as db_session_module

    monkeypatch.setattr(db_session_module, "SessionLocal", lambda: FakeSession())

    with cli.build_worker() as worker:
        assert worker is not None

    assert closed == [True]


def test_default_worker_factory_closes_session_after_worker_exception(monkeypatch) -> None:
    closed = []

    class FakeSession:
        def close(self):
            closed.append(True)

    class FailingWorker:
        def __init__(self, *args, **kwargs):
            pass

        def process_due_batch(self, *, limit=None):
            raise RuntimeError("unsafe-api-secret signature raw payload lease_token")

    monkeypatch.setattr(cli, "ExecutionReconciliationWorkerService", FailingWorker)

    import app.db.session as db_session_module

    monkeypatch.setattr(db_session_module, "SessionLocal", lambda: FakeSession())

    try:
        cli.run_once(batch_size=1, worker_factory=cli.build_worker)
    except RuntimeError:
        pass

    assert closed == [True]


def settings(*, batch_size: int):
    return SimpleNamespace(binance_testnet_reconciliation_batch_size=batch_size)


def summary_with_unsafe_result(unsafe_failure_category: str | None = None) -> AutomaticReconciliationBatchSummary:
    return AutomaticReconciliationBatchSummary(
        claimed_count=2,
        processed_count=2,
        resolved_count=1,
        retried_count=1,
        exhausted_count=0,
        stale_count=0,
        results=[
            AutomaticReconciliationJobResult(
                job_id=1,
                execution_attempt_id=2,
                outcome="retried",
                resolution="failed",
                failure_category=unsafe_failure_category,
                automatic_attempt_count=1,
            )
        ],
    )


def fake_worker_factory(
    calls: list[int],
    *,
    summary: AutomaticReconciliationBatchSummary | None = None,
    unsafe_failure_category: str | None = None,
):
    class FakeWorker:
        def process_due_batch(self, *, limit=None):
            calls.append(limit)
            return summary or summary_with_unsafe_result(unsafe_failure_category)

    @contextmanager
    def factory():
        yield FakeWorker()

    return factory


def failing_worker_factory(message: str):
    class FailingWorker:
        def process_due_batch(self, *, limit=None):
            raise RuntimeError(message)

    @contextmanager
    def factory():
        yield FailingWorker()

    return factory


def fail_if_called(*args, **kwargs):
    raise AssertionError("CLI must not submit Binance orders")
