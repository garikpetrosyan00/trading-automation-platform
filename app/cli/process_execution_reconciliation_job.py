import json
import sys
from contextlib import contextmanager
from typing import Callable, Iterator, TextIO

from app.core.config import get_settings
from app.services.execution_reconciliation_worker import (
    AutomaticReconciliationBatchSummary,
    AutomaticReconciliationJobResult,
    ExecutionReconciliationWorkerService,
)

SAFE_OUTCOMES = {"resolved", "retried", "exhausted", "stale"}
SAFE_RESOLUTIONS = {"found", "not_found", "failed", "already_resolved"}
SAFE_FAILURE_CATEGORIES = {
    "config_unavailable",
    "http_error",
    "invalid_response",
    "mismatched_response",
    "network_error",
    "timeout",
}


@contextmanager
def build_worker() -> Iterator[ExecutionReconciliationWorkerService]:
    from app.db.session import SessionLocal
    from app.repositories.execution_attempt import ExecutionAttemptRepository
    from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
    from app.services.brokers.binance import BinanceTestnetOrderClient

    settings = get_settings()
    db = SessionLocal()
    try:
        attempt_repository = ExecutionAttemptRepository(db)
        order_client = BinanceTestnetOrderClient(
            base_url=settings.binance_testnet_base_url,
            api_key=settings.binance_testnet_api_key or "",
            timeout_seconds=settings.binance_testnet_timeout_seconds,
        )
        yield ExecutionReconciliationWorkerService(
            attempt_repository,
            ExecutionReconciliationJobRepository(db),
            settings=settings,
            order_client=order_client,
        )
    finally:
        db.close()


WorkerFactory = Callable[[], Iterator[ExecutionReconciliationWorkerService]]


def run_once(*, worker_factory: WorkerFactory = build_worker) -> dict:
    with worker_factory() as worker:
        summary = worker.process_due_job()
    return _safe_summary(summary)


def main(
    argv: list[str] | None = None,
    *,
    worker_factory: WorkerFactory = build_worker,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    if argv is None:
        argv = sys.argv[1:]
    if argv in (["-h"], ["--help"]):
        print("Process at most one due Binance testnet reconciliation job and exit.", file=stdout)
        return 0
    if argv:
        print("error: this command accepts no arguments", file=stderr)
        return 2

    try:
        summary = run_once(worker_factory=worker_factory)
    except Exception:
        print("error: execution reconciliation job command failed", file=stderr)
        return 1

    print(json.dumps(summary, sort_keys=True), file=stdout)
    return 0


def _safe_summary(summary: AutomaticReconciliationBatchSummary) -> dict:
    return {
        "due_job_found": summary.claimed_count > 0,
        "processed": summary.processed_count > 0,
        "claimed_count": summary.claimed_count,
        "processed_count": summary.processed_count,
        "resolved_count": summary.resolved_count,
        "retried_count": summary.retried_count,
        "exhausted_count": summary.exhausted_count,
        "stale_count": summary.stale_count,
        "results": [_safe_result(result) for result in summary.results[:1]],
    }


def _safe_result(result: AutomaticReconciliationJobResult) -> dict:
    safe = {
        "job_id": result.job_id,
        "execution_attempt_id": result.execution_attempt_id,
        "outcome": _allowlisted(result.outcome, SAFE_OUTCOMES),
    }
    if result.resolution is not None:
        safe["resolution"] = _allowlisted(result.resolution, SAFE_RESOLUTIONS)
    if result.failure_category is not None:
        safe["failure_category"] = _allowlisted(result.failure_category, SAFE_FAILURE_CATEGORIES)
    if result.automatic_attempt_count is not None:
        safe["automatic_attempt_count"] = result.automatic_attempt_count
    return safe


def _allowlisted(value: str, allowed: set[str]) -> str:
    return value if value in allowed else "other"


if __name__ == "__main__":
    raise SystemExit(main())
