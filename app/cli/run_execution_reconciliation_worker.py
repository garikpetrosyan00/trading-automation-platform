import json
import signal
import sys
import time
from contextlib import contextmanager
from typing import Callable, TextIO

from app.cli.process_execution_reconciliation_job import WorkerFactory, _safe_summary, build_worker
from app.core.config import Settings, get_settings
from app.services.execution_reconciliation_worker import AutomaticReconciliationBatchSummary
from app.services.execution_reconciliation_worker_status import ExecutionReconciliationWorkerStatusService


class StopController:
    def __init__(self) -> None:
        self.stop_requested = False

    def request_stop(self, signum=None, frame=None) -> None:
        self.stop_requested = True


@contextmanager
def build_heartbeat_service(settings: Settings):
    from app.db.session import SessionLocal
    from app.repositories.execution_reconciliation_worker_status import ExecutionReconciliationWorkerStatusRepository

    db = SessionLocal()
    try:
        yield ExecutionReconciliationWorkerStatusService(
            ExecutionReconciliationWorkerStatusRepository(db),
            settings=settings,
        )
    finally:
        db.close()


HeartbeatServiceFactory = Callable[[Settings], object]


def run_loop(
    *,
    settings: Settings,
    worker_factory: WorkerFactory = build_worker,
    heartbeat_service_factory: HeartbeatServiceFactory = build_heartbeat_service,
    sleep: Callable[[int], None] = time.sleep,
    stdout: TextIO | None = None,
    stop_controller: StopController | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stop_controller = stop_controller or StopController()
    interval = settings.binance_testnet_reconciliation_worker_poll_interval_seconds

    with heartbeat_service_factory(settings) as heartbeat_service:
        heartbeat_service.mark_worker_started()
    print(_json_line("worker_started", worker_enabled=True, poll_interval_seconds=interval), file=stdout)
    while not stop_controller.stop_requested:
        try:
            with heartbeat_service_factory(settings) as heartbeat_service:
                heartbeat_service.mark_cycle_started()
            with worker_factory() as worker:
                summary = worker.process_due_job()
            result_code = _cycle_result_code(summary)
            processed_job_id = _processed_job_id(summary)
            with heartbeat_service_factory(settings) as heartbeat_service:
                heartbeat_service.mark_cycle_completed(
                    result_code=result_code,
                    processed_reconciliation_job_id=processed_job_id,
                )
            print(
                json.dumps(
                    {
                        "event": "worker_cycle_completed",
                        "worker_enabled": True,
                        "poll_interval_seconds": interval,
                        **_safe_summary(summary),
                    },
                    sort_keys=True,
                ),
                file=stdout,
            )
        except Exception:
            with heartbeat_service_factory(settings) as heartbeat_service:
                heartbeat_service.mark_cycle_failed()
            print(_json_line("worker_cycle_failed", worker_enabled=True, poll_interval_seconds=interval), file=stdout)

        if stop_controller.stop_requested:
            break
        sleep(interval)

    with heartbeat_service_factory(settings) as heartbeat_service:
        heartbeat_service.mark_worker_stopped()
    print(_json_line("worker_stopped", worker_enabled=True, poll_interval_seconds=interval), file=stdout)
    return 0


def main(
    argv: list[str] | None = None,
    *,
    worker_factory: WorkerFactory = build_worker,
    heartbeat_service_factory: HeartbeatServiceFactory = build_heartbeat_service,
    settings_provider: Callable[[], Settings] = get_settings,
    sleep: Callable[[int], None] = time.sleep,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    install_signal_handlers: bool = True,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    if argv is None:
        argv = sys.argv[1:]
    if argv in (["-h"], ["--help"]):
        print("Run the standalone Binance testnet reconciliation worker until stopped.", file=stdout)
        return 0
    if argv:
        print("error: this command accepts no arguments", file=stderr)
        return 2

    settings = settings_provider()
    if not settings.binance_testnet_reconciliation_worker_enabled:
        print(_json_line("worker_disabled", worker_enabled=False), file=stdout)
        return 0

    stop_controller = StopController()
    previous_handlers = {}
    if install_signal_handlers:
        previous_handlers = _install_signal_handlers(stop_controller)
    try:
        return run_loop(
            settings=settings,
            worker_factory=worker_factory,
            heartbeat_service_factory=heartbeat_service_factory,
            sleep=sleep,
            stdout=stdout,
            stop_controller=stop_controller,
        )
    finally:
        if install_signal_handlers:
            _restore_signal_handlers(previous_handlers)


def _install_signal_handlers(stop_controller: StopController) -> dict[int, signal.Handlers]:
    previous_handlers = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, stop_controller.request_stop)
    return previous_handlers


def _restore_signal_handlers(previous_handlers: dict[int, signal.Handlers]) -> None:
    for signum, previous_handler in previous_handlers.items():
        signal.signal(signum, previous_handler)


def _json_line(event: str, **fields) -> str:
    return json.dumps({"event": event, **fields}, sort_keys=True)


def _cycle_result_code(summary: AutomaticReconciliationBatchSummary) -> str:
    if not summary.results:
        return "no_due_job"
    result = summary.results[0]
    if result.resolution == "failed" and result.failure_category is not None:
        return result.failure_category
    if result.resolution is not None:
        return result.resolution
    return result.outcome


def _processed_job_id(summary: AutomaticReconciliationBatchSummary) -> int | None:
    if not summary.results:
        return None
    return summary.results[0].job_id


if __name__ == "__main__":
    raise SystemExit(main())
