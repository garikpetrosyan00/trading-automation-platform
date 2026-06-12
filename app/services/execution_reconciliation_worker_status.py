from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.models.execution_reconciliation_worker_status import ExecutionReconciliationWorkerStatus
from app.repositories.execution_reconciliation_worker_status import ExecutionReconciliationWorkerStatusRepository

BINANCE_TESTNET_RECONCILIATION_WORKER_NAME = "binance_testnet_reconciliation_worker"
SAFE_WORKER_CYCLE_RESULT_CODES = {
    "already_resolved",
    "exhausted",
    "failed",
    "found",
    "network_error",
    "no_due_job",
    "not_found",
    "retried",
    "stale",
    "timeout",
    "worker_cycle_failed",
}


@dataclass(frozen=True)
class ExecutionReconciliationWorkerStatusSnapshot:
    worker_name: str
    initialized: bool
    configured_enabled: bool
    state: str | None
    last_started_at: datetime | None
    last_heartbeat_at: datetime | None
    last_stopped_at: datetime | None
    last_cycle_started_at: datetime | None
    last_cycle_finished_at: datetime | None
    last_cycle_result_code: str | None
    last_processed_reconciliation_job_id: int | None
    heartbeat_stale_after_seconds: int
    is_stale: bool
    updated_at: datetime | None


class ExecutionReconciliationWorkerStatusService:
    def __init__(
        self,
        repository: ExecutionReconciliationWorkerStatusRepository,
        *,
        settings: Settings,
        now_provider=None,
        worker_name: str = BINANCE_TESTNET_RECONCILIATION_WORKER_NAME,
    ):
        self.repository = repository
        self.settings = settings
        self.now_provider = now_provider or self._utc_now
        self.worker_name = worker_name

    def mark_worker_started(self) -> ExecutionReconciliationWorkerStatus:
        now = self.now_provider()
        status = self.repository.get_or_create(self.worker_name)
        status.state = "running"
        status.last_started_at = now
        status.last_heartbeat_at = now
        status.last_stopped_at = None
        self.repository.db.add(status)
        self.repository.db.commit()
        self.repository.db.refresh(status)
        return status

    def mark_cycle_started(self) -> ExecutionReconciliationWorkerStatus:
        now = self.now_provider()
        status = self.repository.get_or_create(self.worker_name)
        status.state = "running"
        status.last_heartbeat_at = now
        status.last_cycle_started_at = now
        self.repository.db.add(status)
        self.repository.db.commit()
        self.repository.db.refresh(status)
        return status

    def mark_cycle_completed(
        self,
        *,
        result_code: str,
        processed_reconciliation_job_id: int | None = None,
    ) -> ExecutionReconciliationWorkerStatus:
        now = self.now_provider()
        status = self.repository.get_or_create(self.worker_name)
        status.state = "running"
        status.last_heartbeat_at = now
        status.last_cycle_finished_at = now
        status.last_cycle_result_code = self.safe_result_code(result_code)
        status.last_processed_reconciliation_job_id = processed_reconciliation_job_id
        self.repository.db.add(status)
        self.repository.db.commit()
        self.repository.db.refresh(status)
        return status

    def mark_cycle_failed(self) -> ExecutionReconciliationWorkerStatus:
        return self.mark_cycle_completed(result_code="worker_cycle_failed", processed_reconciliation_job_id=None)

    def mark_worker_stopped(self) -> ExecutionReconciliationWorkerStatus:
        now = self.now_provider()
        status = self.repository.get_or_create(self.worker_name)
        status.state = "stopped"
        status.last_heartbeat_at = now
        status.last_stopped_at = now
        self.repository.db.add(status)
        self.repository.db.commit()
        self.repository.db.refresh(status)
        return status

    def get_status(self) -> ExecutionReconciliationWorkerStatusSnapshot:
        status = self.repository.get_by_worker_name(self.worker_name)
        stale_after_seconds = self.settings.binance_testnet_reconciliation_worker_heartbeat_stale_after_seconds
        if status is None:
            return ExecutionReconciliationWorkerStatusSnapshot(
                worker_name=self.worker_name,
                initialized=False,
                configured_enabled=self.settings.binance_testnet_reconciliation_worker_enabled,
                state=None,
                last_started_at=None,
                last_heartbeat_at=None,
                last_stopped_at=None,
                last_cycle_started_at=None,
                last_cycle_finished_at=None,
                last_cycle_result_code=None,
                last_processed_reconciliation_job_id=None,
                heartbeat_stale_after_seconds=stale_after_seconds,
                is_stale=False,
                updated_at=None,
            )

        return ExecutionReconciliationWorkerStatusSnapshot(
            worker_name=status.worker_name,
            initialized=True,
            configured_enabled=self.settings.binance_testnet_reconciliation_worker_enabled,
            state=status.state,
            last_started_at=status.last_started_at,
            last_heartbeat_at=status.last_heartbeat_at,
            last_stopped_at=status.last_stopped_at,
            last_cycle_started_at=status.last_cycle_started_at,
            last_cycle_finished_at=status.last_cycle_finished_at,
            last_cycle_result_code=self.safe_result_code(status.last_cycle_result_code),
            last_processed_reconciliation_job_id=status.last_processed_reconciliation_job_id,
            heartbeat_stale_after_seconds=stale_after_seconds,
            is_stale=self._is_stale(status.last_heartbeat_at, stale_after_seconds=stale_after_seconds),
            updated_at=status.updated_at,
        )

    @staticmethod
    def safe_result_code(value: str | None) -> str | None:
        if value is None:
            return None
        return value if value in SAFE_WORKER_CYCLE_RESULT_CODES else "other"

    def _is_stale(self, last_heartbeat_at: datetime | None, *, stale_after_seconds: int) -> bool:
        heartbeat_at = self._as_utc(last_heartbeat_at)
        if heartbeat_at is None:
            return False
        return self._as_utc(self.now_provider()) - heartbeat_at > timedelta(seconds=stale_after_seconds)

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)
