from dataclasses import dataclass
from datetime import datetime, timedelta
from secrets import token_urlsafe

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.execution_reconciliation_job import ExecutionReconciliationJob


@dataclass(frozen=True)
class ClaimedReconciliationJob:
    id: int
    execution_attempt_id: int
    bot_id: int
    lease_token: str
    lease_expires_at: datetime
    automatic_attempt_count: int


class ExecutionReconciliationJobRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, job_id: int) -> ExecutionReconciliationJob | None:
        return self.db.scalar(select(ExecutionReconciliationJob).where(ExecutionReconciliationJob.id == job_id))

    def get_by_execution_attempt_id(self, execution_attempt_id: int) -> ExecutionReconciliationJob | None:
        return self.db.scalar(
            select(ExecutionReconciliationJob).where(
                ExecutionReconciliationJob.execution_attempt_id == execution_attempt_id
            )
        )

    def list_for_bot_attempt_ids(self, *, bot_id: int, attempt_ids: list[int]) -> dict[int, ExecutionReconciliationJob]:
        if not attempt_ids:
            return {}
        statement = select(ExecutionReconciliationJob).where(
            ExecutionReconciliationJob.bot_id == bot_id,
            ExecutionReconciliationJob.execution_attempt_id.in_(attempt_ids),
        )
        return {job.execution_attempt_id: job for job in self.db.scalars(statement).all()}

    def list_for_bot(self, *, bot_id: int) -> list[ExecutionReconciliationJob]:
        statement = select(ExecutionReconciliationJob).where(ExecutionReconciliationJob.bot_id == bot_id)
        return list(self.db.scalars(statement).all())

    def create_pending(
        self,
        *,
        execution_attempt_id: int,
        bot_id: int,
        next_attempt_at: datetime,
    ) -> ExecutionReconciliationJob:
        job = ExecutionReconciliationJob(
            execution_attempt_id=execution_attempt_id,
            bot_id=bot_id,
            state="pending",
            next_attempt_at=next_attempt_at,
            lease_token=None,
            lease_expires_at=None,
            automatic_attempt_count=0,
        )
        self.db.add(job)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = self.get_by_execution_attempt_id(execution_attempt_id)
            if existing is None:
                raise
            return existing
        return job

    def claim_due_jobs(self, *, now: datetime, lease_seconds: int, limit: int) -> list[ClaimedReconciliationJob]:
        if limit <= 0 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")

        due_filter = or_(
            and_(
                ExecutionReconciliationJob.state == "pending",
                ExecutionReconciliationJob.next_attempt_at <= now,
            ),
            and_(
                ExecutionReconciliationJob.state == "claimed",
                ExecutionReconciliationJob.lease_expires_at <= now,
            ),
        )
        statement = (
            select(ExecutionReconciliationJob)
            .where(due_filter)
            .order_by(ExecutionReconciliationJob.next_attempt_at.asc(), ExecutionReconciliationJob.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = list(self.db.scalars(statement).all())
        claimed: list[ClaimedReconciliationJob] = []
        for job in jobs:
            lease_token = token_urlsafe(32)
            lease_expires_at = now + timedelta(seconds=lease_seconds)
            job.state = "claimed"
            job.lease_token = lease_token
            job.lease_expires_at = lease_expires_at
            self.db.add(job)
            claimed.append(
                ClaimedReconciliationJob(
                    id=job.id,
                    execution_attempt_id=job.execution_attempt_id,
                    bot_id=job.bot_id,
                    lease_token=lease_token,
                    lease_expires_at=lease_expires_at,
                    automatic_attempt_count=job.automatic_attempt_count,
                )
            )
        self.db.commit()
        return claimed

    def release_claimed_job_for_retry(
        self,
        *,
        job_id: int,
        lease_token: str,
        next_attempt_at: datetime,
        checked_at: datetime,
        resolution: str,
        failure_category: str | None,
    ) -> ExecutionReconciliationJob | None:
        job = self._owned_claimed_job(job_id=job_id, lease_token=lease_token)
        if job is None:
            return None
        job.state = "pending"
        job.next_attempt_at = next_attempt_at
        job.automatic_attempt_count += 1
        job.last_checked_at = checked_at
        job.last_resolution = self._safe_value(resolution)
        job.last_failure_category = self._safe_value(failure_category)
        job.lease_token = None
        job.lease_expires_at = None
        self.db.add(job)
        self.db.flush()
        return job

    def mark_claimed_job_resolved(
        self,
        *,
        job_id: int,
        lease_token: str,
        checked_at: datetime,
        resolution: str,
    ) -> ExecutionReconciliationJob | None:
        job = self._owned_claimed_job(job_id=job_id, lease_token=lease_token)
        if job is None:
            return None
        job.state = "resolved"
        job.automatic_attempt_count += 1
        job.last_checked_at = checked_at
        job.last_resolution = self._safe_value(resolution)
        job.last_failure_category = None
        job.resolved_at = checked_at
        job.lease_token = None
        job.lease_expires_at = None
        self.db.add(job)
        self.db.flush()
        return job

    def mark_claimed_job_exhausted(
        self,
        *,
        job_id: int,
        lease_token: str,
        checked_at: datetime,
        resolution: str,
        failure_category: str | None,
    ) -> ExecutionReconciliationJob | None:
        job = self._owned_claimed_job(job_id=job_id, lease_token=lease_token)
        if job is None:
            return None
        job.state = "exhausted"
        job.automatic_attempt_count += 1
        job.last_checked_at = checked_at
        job.last_resolution = self._safe_value(resolution)
        job.last_failure_category = self._safe_value(failure_category)
        job.lease_token = None
        job.lease_expires_at = None
        self.db.add(job)
        self.db.flush()
        return job

    def mark_job_resolved_for_attempt(self, *, execution_attempt_id: int, resolved_at: datetime, resolution: str) -> ExecutionReconciliationJob | None:
        job = self.get_by_execution_attempt_id(execution_attempt_id)
        if job is None:
            return None
        job.state = "resolved"
        job.last_checked_at = resolved_at
        job.last_resolution = self._safe_value(resolution)
        job.last_failure_category = None
        job.resolved_at = resolved_at
        job.lease_token = None
        job.lease_expires_at = None
        self.db.add(job)
        self.db.flush()
        return job

    def get_owned_claimed_job(self, *, job_id: int, lease_token: str) -> ExecutionReconciliationJob | None:
        return self._owned_claimed_job(job_id=job_id, lease_token=lease_token)

    def _owned_claimed_job(self, *, job_id: int, lease_token: str) -> ExecutionReconciliationJob | None:
        return self.db.scalar(
            select(ExecutionReconciliationJob).where(
                ExecutionReconciliationJob.id == job_id,
                ExecutionReconciliationJob.state == "claimed",
                ExecutionReconciliationJob.lease_token == lease_token,
            )
        )

    @staticmethod
    def _safe_value(value: str | None) -> str | None:
        if not isinstance(value, str) or not value:
            return None
        return value[:50]
