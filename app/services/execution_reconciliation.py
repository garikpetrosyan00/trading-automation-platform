from typing import Any

from app.models.execution_attempt import ExecutionAttempt
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.schemas.execution import ExecutionReconciliationAttemptRead, ExecutionReconciliationStatusRead


class ExecutionReconciliationStatusService:
    def __init__(self, repository: ExecutionAttemptRepository):
        self.repository = repository

    def get_bot_status(self, *, bot_id: int, limit: int) -> ExecutionReconciliationStatusRead:
        recent_attempts = self.repository.list_reconciliation_related_for_bot(bot_id=bot_id, limit=limit)

        return ExecutionReconciliationStatusRead(
            bot_id=bot_id,
            unresolved_unknown_count=self.repository.count_unresolved_reconciliation_for_bot(bot_id=bot_id),
            recovered_count=self.repository.count_recovered_reconciliation_for_bot(bot_id=bot_id),
            latest_unresolved_at=self.repository.latest_unresolved_reconciliation_at_for_bot(bot_id=bot_id),
            latest_recovered_at=self.repository.latest_recovered_reconciliation_at_for_bot(bot_id=bot_id),
            recent_attempts=[self._build_attempt_read(attempt) for attempt in recent_attempts],
        )

    def _build_attempt_read(self, attempt: ExecutionAttempt) -> ExecutionReconciliationAttemptRead:
        metadata = self._metadata(attempt)
        return ExecutionReconciliationAttemptRead(
            attempt_id=attempt.id,
            bot_id=attempt.bot_id,
            created_at=attempt.created_at,
            symbol=attempt.symbol,
            side=attempt.side,
            quantity=attempt.requested_quantity,
            reason=attempt.final_reason,
            new_client_order_id=self._safe_string(metadata.get("client_order_id")),
            submission_status_unknown=bool(metadata.get("submission_status_unknown")),
            reconciliation_attempted=bool(metadata.get("reconciliation_attempted")),
            reconciliation_trigger=self._safe_string(metadata.get("reconciliation_trigger")),
            reconciliation_resolution=self._safe_string(metadata.get("reconciliation_resolution")),
            submission_recovered=self._submission_recovered(attempt),
            recovered_order_status=self._safe_string(metadata.get("recovered_order_status")),
            binance_order_id=self._safe_string(metadata.get("exchange_order_id")),
        )

    @classmethod
    def _submission_recovered(cls, attempt: ExecutionAttempt) -> bool:
        return bool(cls._metadata(attempt).get("submission_recovered"))

    @staticmethod
    def _metadata(attempt: ExecutionAttempt) -> dict[str, Any]:
        if isinstance(attempt.metadata_, dict):
            return attempt.metadata_
        return {}

    @staticmethod
    def _safe_string(value: Any) -> str | None:
        if isinstance(value, str) and value:
            return value
        if isinstance(value, int):
            return str(value)
        return None
