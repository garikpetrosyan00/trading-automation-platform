import argparse
import json
import sys
from contextlib import contextmanager
from typing import Callable, Iterator, TextIO

from app.core.config import Settings, get_settings
from app.services.execution_reconciliation_worker import (
    AutomaticReconciliationBatchSummary,
    ExecutionReconciliationWorkerService,
)

MAX_BATCH_SIZE = 100


class CliArgumentError(Exception):
    pass


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(message)


@contextmanager
def build_worker() -> Iterator[ExecutionReconciliationWorkerService]:
    from app.db.session import SessionLocal
    from app.repositories.execution_attempt import ExecutionAttemptRepository
    from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository

    db = SessionLocal()
    try:
        attempt_repository = ExecutionAttemptRepository(db)
        yield ExecutionReconciliationWorkerService(
            attempt_repository,
            ExecutionReconciliationJobRepository(db),
            settings=get_settings(),
        )
    finally:
        db.close()


WorkerFactory = Callable[[], Iterator[ExecutionReconciliationWorkerService]]


def run_once(
    *,
    batch_size: int | None = None,
    worker_factory: WorkerFactory = build_worker,
) -> dict[str, int]:
    with worker_factory() as worker:
        summary = worker.process_due_batch(limit=batch_size)
    return _safe_summary(summary)


def main(
    argv: list[str] | None = None,
    *,
    worker_factory: WorkerFactory = build_worker,
    settings_provider: Callable[[], Settings] = get_settings,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        configured_limit = settings_provider().binance_testnet_reconciliation_batch_size
        batch_size = args.batch_size if args.batch_size is not None else configured_limit
        _validate_batch_size(batch_size)
        summary = run_once(batch_size=batch_size, worker_factory=worker_factory)
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception:
        print("error: automatic reconciliation command failed", file=stderr)
        return 1

    print(json.dumps(summary, sort_keys=True), file=stdout)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="process-binance-testnet-reconciliation",
        description="Process exactly one bounded Binance testnet reconciliation batch and exit.",
    )
    parser.add_argument(
        "--batch-size",
        type=_positive_int,
        default=None,
        help=f"maximum jobs to claim and process once; must be 1-{MAX_BATCH_SIZE}",
    )
    return parser


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("batch size must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("batch size must be greater than zero")
    return parsed


def _validate_batch_size(batch_size: int) -> None:
    if batch_size <= 0:
        raise CliArgumentError("batch size must be greater than zero")
    if batch_size > MAX_BATCH_SIZE:
        raise CliArgumentError(f"batch size must be at most {MAX_BATCH_SIZE}")


def _safe_summary(summary: AutomaticReconciliationBatchSummary) -> dict[str, int]:
    return {
        "claimed_count": summary.claimed_count,
        "processed_count": summary.processed_count,
        "resolved_count": summary.resolved_count,
        "retried_count": summary.retried_count,
        "exhausted_count": summary.exhausted_count,
        "stale_count": summary.stale_count,
    }


if __name__ == "__main__":
    raise SystemExit(main())
