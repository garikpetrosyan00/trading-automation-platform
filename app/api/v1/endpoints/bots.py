from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import DbSession
from app.repositories.bot import BotRepository
from app.repositories.strategy import StrategyRepository
from app.schemas.bot import BotCreate, BotRead, BotStatus, BotUpdate
from app.services.bot import BotService

router = APIRouter()


def get_bot_service(db: DbSession) -> BotService:
    return BotService(BotRepository(db), StrategyRepository(db))


@router.post("", response_model=BotRead, status_code=status.HTTP_201_CREATED)
async def create_bot(payload: BotCreate, db: DbSession) -> BotRead:
    service = get_bot_service(db)
    bot = service.create(payload)
    return BotRead.model_validate(bot)


@router.get("", response_model=list[BotRead])
async def list_bots(
    db: DbSession,
    strategy_id: int | None = Query(default=None),
    status: BotStatus | None = Query(default=None),
) -> list[BotRead]:
    service = get_bot_service(db)
    bots = service.list_all(strategy_id=strategy_id, status=status)
    return [BotRead.model_validate(bot) for bot in bots]


@router.get("/{bot_id}", response_model=BotRead)
async def get_bot(bot_id: int, db: DbSession) -> BotRead:
    service = get_bot_service(db)
    bot = service.get_by_id(bot_id)
    return BotRead.model_validate(bot)


@router.patch("/{bot_id}", response_model=BotRead)
async def update_bot(bot_id: int, payload: BotUpdate, db: DbSession) -> BotRead:
    service = get_bot_service(db)
    bot = service.update(bot_id, payload)
    return BotRead.model_validate(bot)


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(bot_id: int, db: DbSession) -> Response:
    service = get_bot_service(db)
    service.delete(bot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
