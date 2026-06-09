from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.execution_attempt import ExecutionAttempt
from app.models.execution_reconciliation_job import ExecutionReconciliationJob
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository


@dataclass(frozen=True)
class EnqueueReconciliationJobResult:
    enqueued: bool
    reason: str
    job: ExecutionReconciliationJob | None = None


@dataclass(frozen=True)
class ReconciliationJobCounts:
    pending: int
    claimed: int
    expired: int
    exhausted: int


class ExecutionReconciliationJobService:
    def __init__(
        self,
        attempt_repository: ExecutionAttemptRepository,
        job_repository: ExecutionReconciliationJobRepository | None = None,
        *,
        now_provider=None,
    ):
        self.attempt_repository = attempt_repository
        self.job_repository = job_repository or ExecutionReconciliationJobRepository(attempt_repository.db)
        self.now_provider = now_provider or self._utc_now

    def ensure_pending_job_for_attempt(
        self,
        *,
        execution_attempt_id: int,
        next_attempt_at: datetime,
    ) -> EnqueueReconciliationJobResult:
        attempt = self.attempt_repository.get_by_id(execution_attempt_id)
        if attempt is None:
            return EnqueueReconciliationJobResult(False, "attempt_not_found")
        eligibility = self._eligibility_reason(attempt)
        if eligibility != "eligible":
            return EnqueueReconciliationJobResult(False, eligibility)

        existing = self.job_repository.get_by_execution_attempt_id(execution_attempt_id)
        if existing is not None:
            if existing.state == "resolved":
                return EnqueueReconciliationJobResult(False, "already_resolved", existing)
            lease_expires_at = self._as_utc(existing.lease_expires_at)
            if existing.state == "claimed" and lease_expires_at is not None and lease_expires_at > self.now_provider():
                return EnqueueReconciliationJobResult(False, "active_claim_exists", existing)
            return EnqueueReconciliationJobResult(True, "already_exists", existing)

        job = self.job_repository.create_pending(
            execution_attempt_id=attempt.id,
            bot_id=attempt.bot_id,
            next_attempt_at=next_attempt_at,
        )
        return EnqueueReconciliationJobResult(True, "created", job)

    def ensure_pending_job_for_persisted_attempt(
        self,
        attempt: ExecutionAttempt,
        *,
        initial_delay_seconds: int,
    ) -> EnqueueReconciliationJobResult:
        created_at = self._as_utc(attempt.created_at) or self.now_provider()
        next_attempt_at = created_at + timedelta(seconds=initial_delay_seconds)
        return self.ensure_pending_job_for_attempt(
            execution_attempt_id=attempt.id,
            next_attempt_at=next_attempt_at,
        )

    def mark_job_resolved_for_attempt(self, *, execution_attempt_id: int, resolved_at: datetime) -> ExecutionReconciliationJob | None:
        return self.job_repository.mark_job_resolved_for_attempt(
            execution_attempt_id=execution_attempt_id,
            resolved_at=resolved_at,
            resolution="found",
        )

    def counts_for_bot(self, *, bot_id: int) -> ReconciliationJobCounts:
        now = self.now_provider()
        all_jobs = self.job_repository.list_for_bot(bot_id=bot_id)
        return ReconciliationJobCounts(
            pending=sum(1 for job in all_jobs if job.state == "pending"),
            claimed=sum(1 for job in all_jobs if job.state == "claimed"),
            expired=sum(
                1
                for job in all_jobs
                if job.state == "claimed"
                and self._as_utc(job.lease_expires_at) is not None
                and self._as_utc(job.lease_expires_at) <= now
            ),
            exhausted=sum(1 for job in all_jobs if job.state == "exhausted"),
        )

    def jobs_for_attempts(self, *, bot_id: int, attempt_ids: list[int]) -> dict[int, ExecutionReconciliationJob]:
        return self.job_repository.list_for_bot_attempt_ids(bot_id=bot_id, attempt_ids=attempt_ids)

    def eligibility_reason_for_attempt(self, attempt: ExecutionAttempt) -> str:
        return self._eligibility_reason(attempt)

    def _eligibility_reason(self, attempt: ExecutionAttempt) -> str:
        metadata = self._metadata(attempt)
        if attempt.bot_id is None:
            return "missing_bot"
        if attempt.mode != "testnet" or attempt.broker != "binance_testnet":
            return "wrong_mode_or_broker"
        if metadata.get("submission_status_unknown") is not True:
            return "not_status_unknown"
        if metadata.get("submission_recovered") is True:
            return "already_recovered"
        if self._safe_string(metadata.get("reconciliation_resolution")) != "unresolved":
            return "not_unresolved"
        if not self._safe_symbol(attempt.symbol):
            return "missing_symbol"
        if not self._safe_string(metadata.get("client_order_id")):
            return "missing_client_order_id"
        return "eligible"

    @staticmethod
    def _metadata(attempt: ExecutionAttempt) -> dict[str, Any]:
        if isinstance(attempt.metadata_, dict):
            return attempt.metadata_
        return {}

    @staticmethod
    def _safe_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _safe_symbol(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().upper()
        return normalized or None

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
