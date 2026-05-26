from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import DbSession
from app.core.errors import NotFoundError
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.portfolio import PortfolioRepository
from app.schemas.execution import (
    ExecutionAuditMode,
    ExecutionAuditStatus,
    ExecutionFillAuditRead,
    ExecutionOrderAuditRead,
    ExecutionSide,
)

router = APIRouter()

OrderLimit = Annotated[int, Query(ge=1, le=100)]


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


def _normalize_symbol_filter(symbol: str | None) -> str | None:
    if symbol is None:
        return None
    normalized = symbol.strip().upper()
    return normalized or None
