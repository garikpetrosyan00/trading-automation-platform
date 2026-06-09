from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError
from app.models.execution_attempt import ExecutionAttempt
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ClaimedReconciliationJob, ExecutionReconciliationJobRepository
from app.services.brokers.binance import BinanceTestnetOrderClient
from app.services.execution_reconciliation import ExecutionReconciliationStatusService
from app.services.execution_reconciliation_jobs import ExecutionReconciliationJobService


@dataclass(frozen=True)
class AutomaticReconciliationJobResult:
    job_id: int
    execution_attempt_id: int
    outcome: str
    resolution: str | None = None
    failure_category: str | None = None
    automatic_attempt_count: int | None = None


@dataclass(frozen=True)
class AutomaticReconciliationBatchSummary:
    claimed_count: int
    processed_count: int
    resolved_count: int
    retried_count: int
    exhausted_count: int
    stale_count: int
    results: list[AutomaticReconciliationJobResult] = field(default_factory=list)


class ExecutionReconciliationWorkerService:
    def __init__(
        self,
        attempt_repository: ExecutionAttemptRepository,
        job_repository: ExecutionReconciliationJobRepository | None = None,
        *,
        settings: Settings | None = None,
        order_client: BinanceTestnetOrderClient | None = None,
        timestamp_provider=None,
        now_provider=None,
    ):
        self.attempt_repository = attempt_repository
        self.job_repository = job_repository or ExecutionReconciliationJobRepository(attempt_repository.db)
        self.settings = settings
        self.order_client = order_client
        self.timestamp_provider = timestamp_provider
        self.now_provider = now_provider or self._utc_now

    def process_due_batch(self, *, limit: int | None = None) -> AutomaticReconciliationBatchSummary:
        settings = self._settings()
        batch_limit = limit if limit is not None else settings.binance_testnet_reconciliation_batch_size
        claimed_jobs = self.job_repository.claim_due_jobs(
            now=self.now_provider(),
            lease_seconds=settings.binance_testnet_reconciliation_lease_seconds,
            limit=batch_limit,
        )
        results = [self._process_claimed_job(claimed_job) for claimed_job in claimed_jobs]
        return AutomaticReconciliationBatchSummary(
            claimed_count=len(claimed_jobs),
            processed_count=sum(1 for result in results if result.outcome != "stale"),
            resolved_count=sum(1 for result in results if result.outcome == "resolved"),
            retried_count=sum(1 for result in results if result.outcome == "retried"),
            exhausted_count=sum(1 for result in results if result.outcome == "exhausted"),
            stale_count=sum(1 for result in results if result.outcome == "stale"),
            results=results,
        )

    def _process_claimed_job(self, claimed_job: ClaimedReconciliationJob) -> AutomaticReconciliationJobResult:
        if (
            self.job_repository.get_owned_claimed_job(
                job_id=claimed_job.id,
                lease_token=claimed_job.lease_token,
            )
            is None
        ):
            self.attempt_repository.db.rollback()
            return self._stale_result(claimed_job)

        attempt = self.attempt_repository.get_by_id(claimed_job.execution_attempt_id)
        if attempt is None:
            return self._finish_terminal(
                claimed_job,
                resolution="failed",
                failure_category="missing_attempt",
                record_attempt_metadata=False,
            )
        if self._submission_recovered(attempt):
            return self._resolve_without_query(claimed_job, resolution="already_resolved")

        eligibility = self._job_service().eligibility_reason_for_attempt(attempt)
        if eligibility != "eligible":
            return self._finish_terminal(
                claimed_job,
                resolution="failed",
                failure_category=eligibility,
                record_attempt_metadata=False,
            )

        metadata = self._safe_metadata(attempt)
        symbol = self._safe_symbol(attempt.symbol)
        client_order_id = self._safe_string(metadata.get("client_order_id"))
        if symbol is None or client_order_id is None:
            return self._finish_terminal(
                claimed_job,
                resolution="failed",
                failure_category="missing_order_lookup_fields",
                record_attempt_metadata=False,
            )

        result = self._query_order(symbol=symbol, client_order_id=client_order_id)
        latest = self.attempt_repository.get_by_id(claimed_job.execution_attempt_id)
        if latest is None:
            return self._finish_terminal(
                claimed_job,
                resolution="failed",
                failure_category="missing_attempt",
                record_attempt_metadata=False,
            )
        if self._submission_recovered(latest):
            return self._resolve_without_query(claimed_job, resolution="already_resolved")

        checked_at = self.now_provider()
        if result["resolution"] == "found":
            return self._mark_attempt_recovered(claimed_job, latest, result["payload"], checked_at=checked_at)

        failure_category = self._safe_string(result.get("failure_category"))
        return self._retry_or_exhaust(
            claimed_job,
            checked_at=checked_at,
            resolution=result["resolution"],
            failure_category=failure_category,
        )

    def _mark_attempt_recovered(
        self,
        claimed_job: ClaimedReconciliationJob,
        attempt: ExecutionAttempt,
        payload: dict[str, Any],
        *,
        checked_at: datetime,
    ) -> AutomaticReconciliationJobResult:
        metadata = self._safe_metadata(attempt)
        attempt.metadata_ = {
            **metadata,
            "client_order_id": self._safe_string(metadata.get("client_order_id")),
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "found",
            "submission_recovered": True,
            "recovered_order_status": self._safe_string(payload.get("status")),
            "exchange_order_id": self._safe_string(payload.get("orderId")),
            "automatic_reconciliation_attempted": True,
            "automatic_reconciliation_last_checked_at": checked_at.isoformat(),
            "automatic_reconciliation_last_resolution": "found",
        }
        attempt.metadata_.pop("automatic_reconciliation_last_failure_category", None)
        attempt.final_status = "order_created"
        attempt.final_reason = "testnet_order_recovered_after_unknown_submission"
        self.attempt_repository.update(attempt)
        job = self.job_repository.mark_claimed_job_resolved(
            job_id=claimed_job.id,
            lease_token=claimed_job.lease_token,
            checked_at=checked_at,
            resolution="found",
        )
        if job is None:
            self.attempt_repository.db.rollback()
            return self._stale_result(claimed_job)
        self.attempt_repository.db.commit()
        return AutomaticReconciliationJobResult(
            job_id=claimed_job.id,
            execution_attempt_id=claimed_job.execution_attempt_id,
            outcome="resolved",
            resolution="found",
            automatic_attempt_count=job.automatic_attempt_count,
        )

    def _retry_or_exhaust(
        self,
        claimed_job: ClaimedReconciliationJob,
        *,
        checked_at: datetime,
        resolution: str,
        failure_category: str | None,
    ) -> AutomaticReconciliationJobResult:
        next_count = claimed_job.automatic_attempt_count + 1
        if next_count >= self._settings().binance_testnet_reconciliation_max_automatic_attempts:
            return self._finish_terminal(
                claimed_job,
                resolution=resolution,
                failure_category=failure_category,
                checked_at=checked_at,
            )

        self._record_unresolved_attempt_metadata(
            claimed_job.execution_attempt_id,
            checked_at=checked_at,
            resolution=resolution,
            failure_category=failure_category,
        )
        job = self.job_repository.release_claimed_job_for_retry(
            job_id=claimed_job.id,
            lease_token=claimed_job.lease_token,
            next_attempt_at=checked_at + timedelta(
                seconds=self._settings().binance_testnet_reconciliation_retry_delay_seconds
            ),
            checked_at=checked_at,
            resolution=resolution,
            failure_category=failure_category,
        )
        if job is None:
            self.attempt_repository.db.rollback()
            return self._stale_result(claimed_job)
        self.attempt_repository.db.commit()
        return AutomaticReconciliationJobResult(
            job_id=claimed_job.id,
            execution_attempt_id=claimed_job.execution_attempt_id,
            outcome="retried",
            resolution=resolution,
            failure_category=failure_category,
            automatic_attempt_count=job.automatic_attempt_count,
        )

    def _finish_terminal(
        self,
        claimed_job: ClaimedReconciliationJob,
        *,
        resolution: str,
        failure_category: str | None,
        checked_at: datetime | None = None,
        record_attempt_metadata: bool = True,
    ) -> AutomaticReconciliationJobResult:
        checked_at = checked_at or self.now_provider()
        if record_attempt_metadata:
            self._record_unresolved_attempt_metadata(
                claimed_job.execution_attempt_id,
                checked_at=checked_at,
                resolution=resolution,
                failure_category=failure_category,
            )
        job = self.job_repository.mark_claimed_job_exhausted(
            job_id=claimed_job.id,
            lease_token=claimed_job.lease_token,
            checked_at=checked_at,
            resolution=resolution,
            failure_category=failure_category,
        )
        if job is None:
            self.attempt_repository.db.rollback()
            return self._stale_result(claimed_job)
        self.attempt_repository.db.commit()
        return AutomaticReconciliationJobResult(
            job_id=claimed_job.id,
            execution_attempt_id=claimed_job.execution_attempt_id,
            outcome="exhausted",
            resolution=resolution,
            failure_category=failure_category,
            automatic_attempt_count=job.automatic_attempt_count,
        )

    def _resolve_without_query(
        self,
        claimed_job: ClaimedReconciliationJob,
        *,
        resolution: str,
    ) -> AutomaticReconciliationJobResult:
        checked_at = self.now_provider()
        job = self.job_repository.mark_claimed_job_resolved(
            job_id=claimed_job.id,
            lease_token=claimed_job.lease_token,
            checked_at=checked_at,
            resolution=resolution,
        )
        if job is None:
            self.attempt_repository.db.rollback()
            return self._stale_result(claimed_job)
        self.attempt_repository.db.commit()
        return AutomaticReconciliationJobResult(
            job_id=claimed_job.id,
            execution_attempt_id=claimed_job.execution_attempt_id,
            outcome="resolved",
            resolution=resolution,
            automatic_attempt_count=job.automatic_attempt_count,
        )

    def _record_unresolved_attempt_metadata(
        self,
        execution_attempt_id: int,
        *,
        checked_at: datetime,
        resolution: str,
        failure_category: str | None,
    ) -> None:
        attempt = self.attempt_repository.get_by_id(execution_attempt_id)
        if attempt is None:
            return
        if self._submission_recovered(attempt):
            return
        metadata = self._safe_metadata(attempt)
        attempt.metadata_ = {
            **metadata,
            "submission_status_unknown": bool(metadata.get("submission_status_unknown")),
            "reconciliation_attempted": bool(metadata.get("reconciliation_attempted")),
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
            "automatic_reconciliation_attempted": True,
            "automatic_reconciliation_last_checked_at": checked_at.isoformat(),
            "automatic_reconciliation_last_resolution": resolution,
        }
        if failure_category is not None:
            attempt.metadata_["automatic_reconciliation_last_failure_category"] = failure_category
        else:
            attempt.metadata_.pop("automatic_reconciliation_last_failure_category", None)
        self.attempt_repository.update(attempt)

    def _query_order(self, *, symbol: str, client_order_id: str) -> dict[str, Any]:
        query_service = ExecutionReconciliationStatusService(
            self.attempt_repository,
            settings=self._settings(),
            order_client=self.order_client,
            timestamp_provider=self.timestamp_provider,
        )
        try:
            return query_service.query_order_status(symbol=symbol, client_order_id=client_order_id)
        except AppError:
            return {"resolution": "failed", "failure_category": "config_unavailable"}

    def _job_service(self) -> ExecutionReconciliationJobService:
        return ExecutionReconciliationJobService(
            self.attempt_repository,
            self.job_repository,
            now_provider=self.now_provider,
        )

    def _settings(self) -> Settings:
        if self.settings is not None:
            return self.settings
        from app.core.config import get_settings

        return get_settings()

    @staticmethod
    def _submission_recovered(attempt: ExecutionAttempt) -> bool:
        return bool(ExecutionReconciliationStatusService._metadata(attempt).get("submission_recovered"))

    @staticmethod
    def _safe_metadata(attempt: ExecutionAttempt) -> dict[str, Any]:
        return ExecutionReconciliationStatusService._safe_metadata(attempt)

    @staticmethod
    def _safe_string(value: Any) -> str | None:
        return ExecutionReconciliationStatusService._safe_string(value)

    @staticmethod
    def _safe_symbol(value: Any) -> str | None:
        return ExecutionReconciliationStatusService._safe_symbol(value)

    @staticmethod
    def _stale_result(claimed_job: ClaimedReconciliationJob) -> AutomaticReconciliationJobResult:
        return AutomaticReconciliationJobResult(
            job_id=claimed_job.id,
            execution_attempt_id=claimed_job.execution_attempt_id,
            outcome="stale",
        )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)
