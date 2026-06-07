from decimal import Decimal
from typing import Any

from app.models.execution_attempt import ExecutionAttempt
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.services.execution_reconciliation_jobs import ExecutionReconciliationJobService


class ExecutionAttemptService:
    def __init__(self, repository: ExecutionAttemptRepository):
        self.repository = repository

    def record(
        self,
        *,
        bot_id: int | None,
        strategy_id: int | None,
        symbol: str,
        side: str,
        mode: str,
        broker: str | None,
        requested_quantity: Decimal,
        requested_price: Decimal | None,
        decision_reason: str | None,
        risk_status: str | None,
        safety_status: str | None,
        final_status: str,
        final_reason: str | None,
        order_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionAttempt:
        attempt = ExecutionAttempt(
            bot_id=bot_id,
            strategy_id=strategy_id,
            symbol=symbol.upper(),
            side=side,
            mode=mode,
            broker=broker,
            requested_quantity=requested_quantity,
            requested_price=requested_price,
            decision_reason=decision_reason,
            risk_status=risk_status,
            safety_status=safety_status,
            final_status=final_status,
            final_reason=final_reason,
            order_id=order_id,
            metadata_=metadata,
        )
        persisted = self.repository.create(attempt)
        self._ensure_reconciliation_job_if_needed(persisted)
        return persisted

    def mark_final(
        self,
        attempt: ExecutionAttempt,
        *,
        final_status: str,
        final_reason: str | None,
        order_id: int | None = None,
        risk_status: str | None = None,
        safety_status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionAttempt:
        attempt.final_status = final_status
        attempt.final_reason = final_reason
        if order_id is not None:
            attempt.order_id = order_id
        if risk_status is not None:
            attempt.risk_status = risk_status
        if safety_status is not None:
            attempt.safety_status = safety_status
        if metadata is not None:
            attempt.metadata_ = metadata
        persisted = self.repository.update(attempt)
        self._ensure_reconciliation_job_if_needed(persisted)
        return persisted

    def _ensure_reconciliation_job_if_needed(self, attempt: ExecutionAttempt) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        ExecutionReconciliationJobService(
            self.repository,
            ExecutionReconciliationJobRepository(self.repository.db),
        ).ensure_pending_job_for_persisted_attempt(
            attempt,
            initial_delay_seconds=settings.binance_testnet_reconciliation_initial_delay_seconds,
        )
