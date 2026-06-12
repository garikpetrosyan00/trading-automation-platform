from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import DbSession
from app.core.errors import NotFoundError
from app.models.execution_attempt import ExecutionAttempt
from app.models.execution_reconciliation_job import ExecutionReconciliationJob
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.bot import BotRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.schemas.execution import (
    ExecutionAuditMode,
    ExecutionAuditStatus,
    ExecutionAttemptMode,
    ExecutionAttemptRead,
    ExecutionAttemptStatus,
    ExecutionFillAuditRead,
    ExecutionManualReconciliationRead,
    ExecutionOrderAuditRead,
    ExecutionReconciliationJobRead,
    ExecutionReconciliationJobStatus,
    ExecutionReconciliationStatusRead,
    ExecutionSide,
)
from app.services.execution_reconciliation import ExecutionReconciliationStatusService
from app.services.metadata_sanitizer import sanitize_public_metadata

router = APIRouter()

OrderLimit = Annotated[int, Query(ge=1, le=100)]
SAFE_RECONCILIATION_RESULT_CODES = {"found", "not_found", "failed", "known_rejected", "already_resolved"}
SAFE_RECONCILIATION_FAILURE_CODES = {
    "active_claim_exists",
    "already_recovered",
    "config_unavailable",
    "http_error",
    "invalid_response",
    "mismatched_response",
    "missing_attempt",
    "missing_bot",
    "missing_client_order_id",
    "missing_order_lookup_fields",
    "missing_symbol",
    "network_error",
    "not_status_unknown",
    "not_unresolved",
    "timeout",
    "wrong_mode_or_broker",
}


@router.get("/orders", response_model=list[ExecutionOrderAuditRead])
async def list_orders(
    db: DbSession,
    bot_id: int | None = Query(default=None, ge=1),
    strategy_id: int | None = Query(default=None, ge=1),
    symbol: str | None = Query(default=None),
    status: ExecutionAuditStatus | None = Query(default=None),
    side: ExecutionSide | None = Query(default=None),
    mode: ExecutionAuditMode | None = Query(default=None),
    limit: OrderLimit = 50,
) -> list[ExecutionOrderAuditRead]:
    repository = PortfolioRepository(db)
    orders = repository.list_orders_filtered(
        bot_id=bot_id,
        strategy_id=strategy_id,
        symbol=_normalize_symbol_filter(symbol),
        status=status,
        side=side,
        mode=mode,
        limit=limit,
    )
    return [_build_order_read(repository, order) for order in orders]


@router.get("/execution-attempts", response_model=list[ExecutionAttemptRead])
async def list_execution_attempts(
    db: DbSession,
    bot_id: int | None = Query(default=None, ge=1),
    strategy_id: int | None = Query(default=None, ge=1),
    symbol: str | None = Query(default=None),
    side: ExecutionSide | None = Query(default=None),
    mode: ExecutionAttemptMode | None = Query(default=None),
    final_status: ExecutionAttemptStatus | None = Query(default=None),
    reason: str | None = Query(default=None),
    limit: OrderLimit = 50,
) -> list[ExecutionAttemptRead]:
    repository = ExecutionAttemptRepository(db)
    attempts = repository.list_filtered(
        bot_id=bot_id,
        strategy_id=strategy_id,
        symbol=_normalize_symbol_filter(symbol),
        side=side,
        mode=mode,
        final_status=final_status,
        reason=reason,
        limit=limit,
    )
    return [_build_attempt_read(attempt) for attempt in attempts]


@router.get("/execution-attempts/{attempt_id}", response_model=ExecutionAttemptRead)
async def get_execution_attempt(attempt_id: int, db: DbSession) -> ExecutionAttemptRead:
    repository = ExecutionAttemptRepository(db)
    attempt = repository.get_by_id(attempt_id)
    if attempt is None:
        raise NotFoundError(
            f"Execution attempt with id {attempt_id} was not found",
            error_code="execution_attempt_not_found",
        )
    return _build_attempt_read(attempt)


@router.get("/execution-reconciliation-jobs", response_model=list[ExecutionReconciliationJobRead])
async def list_execution_reconciliation_jobs(
    db: DbSession,
    status: ExecutionReconciliationJobStatus | None = Query(default=None),
    limit: OrderLimit = 50,
) -> list[ExecutionReconciliationJobRead]:
    jobs = ExecutionReconciliationJobRepository(db).list_filtered(status=status, limit=limit)
    return [_build_reconciliation_job_read(job) for job in jobs]


@router.get("/execution-reconciliation-jobs/{job_id}", response_model=ExecutionReconciliationJobRead)
async def get_execution_reconciliation_job(job_id: int, db: DbSession) -> ExecutionReconciliationJobRead:
    job = ExecutionReconciliationJobRepository(db).get_by_id(job_id)
    if job is None:
        raise NotFoundError(
            f"Execution reconciliation job with id {job_id} was not found",
            error_code="execution_reconciliation_job_not_found",
        )
    return _build_reconciliation_job_read(job)


@router.get("/orders/{order_id}", response_model=ExecutionOrderAuditRead)
async def get_order(order_id: int, db: DbSession) -> ExecutionOrderAuditRead:
    repository = PortfolioRepository(db)
    order = repository.get_order_by_id(order_id)
    if order is None:
        raise NotFoundError(f"Order with id {order_id} was not found", error_code="order_not_found")
    return _build_order_read(repository, order, include_fills=True)


@router.get("/orders/{order_id}/fills", response_model=list[ExecutionFillAuditRead])
async def list_order_fills(order_id: int, db: DbSession) -> list[ExecutionFillAuditRead]:
    repository = PortfolioRepository(db)
    order = repository.get_order_by_id(order_id)
    if order is None:
        raise NotFoundError(f"Order with id {order_id} was not found", error_code="order_not_found")
    return [_build_fill_read(fill) for fill in repository.list_fills_for_order(order_id)]


@router.get("/bots/{bot_id}/orders", response_model=list[ExecutionOrderAuditRead])
async def list_bot_orders(
    bot_id: int,
    db: DbSession,
    status: ExecutionAuditStatus | None = Query(default=None),
    side: ExecutionSide | None = Query(default=None),
    symbol: str | None = Query(default=None),
    mode: ExecutionAuditMode | None = Query(default=None),
    limit: OrderLimit = 50,
) -> list[ExecutionOrderAuditRead]:
    repository = PortfolioRepository(db)
    orders = repository.list_orders_filtered(
        bot_id=bot_id,
        symbol=_normalize_symbol_filter(symbol),
        status=status,
        side=side,
        mode=mode,
        limit=limit,
    )
    return [_build_order_read(repository, order) for order in orders]


@router.get("/bots/{bot_id}/execution-attempts", response_model=list[ExecutionAttemptRead])
async def list_bot_execution_attempts(
    bot_id: int,
    db: DbSession,
    symbol: str | None = Query(default=None),
    side: ExecutionSide | None = Query(default=None),
    mode: ExecutionAttemptMode | None = Query(default=None),
    final_status: ExecutionAttemptStatus | None = Query(default=None),
    reason: str | None = Query(default=None),
    limit: OrderLimit = 50,
) -> list[ExecutionAttemptRead]:
    repository = ExecutionAttemptRepository(db)
    attempts = repository.list_filtered(
        bot_id=bot_id,
        symbol=_normalize_symbol_filter(symbol),
        side=side,
        mode=mode,
        final_status=final_status,
        reason=reason,
        limit=limit,
    )
    return [_build_attempt_read(attempt) for attempt in attempts]


@router.get("/bots/{bot_id}/execution-reconciliation/status", response_model=ExecutionReconciliationStatusRead)
async def get_bot_execution_reconciliation_status(
    bot_id: int,
    db: DbSession,
    limit: OrderLimit = 20,
) -> ExecutionReconciliationStatusRead:
    if BotRepository(db).get_by_id(bot_id) is None:
        raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")
    return ExecutionReconciliationStatusService(ExecutionAttemptRepository(db)).get_bot_status(
        bot_id=bot_id,
        limit=limit,
    )


@router.post(
    "/bots/{bot_id}/execution-attempts/{attempt_id}/reconcile",
    response_model=ExecutionManualReconciliationRead,
)
async def reconcile_bot_execution_attempt(
    bot_id: int,
    attempt_id: int,
    db: DbSession,
) -> ExecutionManualReconciliationRead:
    if BotRepository(db).get_by_id(bot_id) is None:
        raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")
    return ExecutionReconciliationStatusService(ExecutionAttemptRepository(db)).manually_reconcile_attempt(
        bot_id=bot_id,
        attempt_id=attempt_id,
    )


def _build_order_read(
    repository: PortfolioRepository,
    order: SimulatedOrder,
    *,
    include_fills: bool = False,
) -> ExecutionOrderAuditRead:
    fills = repository.list_fills_for_order(order.id) if include_fills else []
    fill_count = len(fills) if include_fills else repository.count_fills_for_order(order.id)
    return ExecutionOrderAuditRead(
        id=order.id,
        bot_id=order.bot_id,
        strategy_id=order.strategy_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        mode=order.mode,
        quantity=order.quantity,
        requested_price=order.requested_price_snapshot,
        requested_price_snapshot=order.requested_price_snapshot,
        status=order.status,
        decision_reason=order.decision_reason,
        decision_metadata=order.decision_metadata,
        rejection_reason=order.rejection_reason,
        fill_count=fill_count,
        fills=[_build_fill_read(fill) for fill in fills],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _build_fill_read(fill: SimulatedFill) -> ExecutionFillAuditRead:
    return ExecutionFillAuditRead(
        id=fill.id,
        order_id=fill.order_id,
        symbol=fill.symbol,
        side=fill.side,
        fill_price=fill.fill_price,
        fill_quantity=fill.fill_quantity,
        fee=fill.fee,
        source=fill.source,
        filled_at=fill.filled_at,
    )


def _build_attempt_read(attempt: ExecutionAttempt) -> ExecutionAttemptRead:
    return ExecutionAttemptRead(
        id=attempt.id,
        bot_id=attempt.bot_id,
        strategy_id=attempt.strategy_id,
        order_id=attempt.order_id,
        symbol=attempt.symbol,
        side=attempt.side,
        mode=attempt.mode,
        broker=attempt.broker,
        requested_quantity=attempt.requested_quantity,
        requested_price=attempt.requested_price,
        decision_reason=attempt.decision_reason,
        risk_status=attempt.risk_status,
        safety_status=attempt.safety_status,
        final_status=attempt.final_status,
        final_reason=attempt.final_reason,
        metadata=sanitize_public_metadata(attempt.metadata_),
        created_at=attempt.created_at,
    )


def _build_reconciliation_job_read(job: ExecutionReconciliationJob) -> ExecutionReconciliationJobRead:
    return ExecutionReconciliationJobRead(
        id=job.id,
        execution_attempt_id=job.execution_attempt_id,
        bot_id=job.bot_id,
        status=job.state,
        automatic_attempt_count=job.automatic_attempt_count,
        next_attempt_at=job.next_attempt_at,
        lease_expires_at=job.lease_expires_at,
        last_checked_at=job.last_checked_at,
        last_result_code=_safe_reconciliation_code(job.last_resolution, SAFE_RECONCILIATION_RESULT_CODES),
        last_failure_code=_safe_reconciliation_code(job.last_failure_category, SAFE_RECONCILIATION_FAILURE_CODES),
        created_at=job.created_at,
        updated_at=job.updated_at,
        resolved_at=job.resolved_at,
    )


def _safe_reconciliation_code(value: str | None, allowed: set[str]) -> str | None:
    if value is None:
        return None
    return value if value in allowed else "other"


def _normalize_symbol_filter(symbol: str | None) -> str | None:
    if symbol is None:
        return None
    normalized = symbol.strip().upper()
    return normalized or None
