from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Query

from app.api.dependencies import DbSession
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.repositories.bot import BotRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_accounting import PaperAccountingRepository
from app.schemas.execution import ExecutionSafetyStatusRead
from app.services.execution_safety_status import ExecutionSafetyStatusService

router = APIRouter()

ExecutionModeQuery = Literal["paper", "testnet", "live"]
ExecutionSideQuery = Literal["buy", "sell"]


@router.get("/execution-safety/status", response_model=ExecutionSafetyStatusRead)
async def get_execution_safety_status(
    db: DbSession,
    mode: ExecutionModeQuery = Query(default="paper"),
    broker: str = Query(default="paper"),
    side: ExecutionSideQuery = Query(default="buy"),
    quantity: Decimal = Query(default=Decimal("1"), gt=0),
    market_price: Decimal | None = Query(default=None, gt=0),
) -> ExecutionSafetyStatusRead:
    return _build_status(
        db,
        bot_id=None,
        mode=mode,
        broker=broker,
        side=side,
        quantity=quantity,
        market_price=market_price,
    )


@router.get("/bots/{bot_id}/execution-safety/status", response_model=ExecutionSafetyStatusRead)
async def get_bot_execution_safety_status(
    bot_id: int,
    db: DbSession,
    mode: ExecutionModeQuery = Query(default="paper"),
    broker: str = Query(default="paper"),
    side: ExecutionSideQuery = Query(default="buy"),
    quantity: Decimal = Query(default=Decimal("1"), gt=0),
    market_price: Decimal | None = Query(default=None, gt=0),
) -> ExecutionSafetyStatusRead:
    if BotRepository(db).get_by_id(bot_id) is None:
        raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")
    return _build_status(
        db,
        bot_id=bot_id,
        mode=mode,
        broker=broker,
        side=side,
        quantity=quantity,
        market_price=market_price,
    )


def _build_status(
    db,
    *,
    bot_id: int | None,
    mode: str,
    broker: str,
    side: str,
    quantity: Decimal,
    market_price: Decimal | None,
) -> ExecutionSafetyStatusRead:
    service = ExecutionSafetyStatusService(
        ExecutionAttemptRepository(db),
        get_settings(),
        paper_accounting_repository=PaperAccountingRepository(db),
    )
    status = service.get_status(
        bot_id=bot_id,
        mode=mode,
        broker=broker,
        side=side,
        quantity=quantity,
        market_price=market_price,
    )
    return ExecutionSafetyStatusRead(**status.__dict__)
