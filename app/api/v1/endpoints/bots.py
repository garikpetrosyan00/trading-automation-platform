from fastapi import APIRouter, Response, status

from app.api.dependencies import BotRunnerDep, DbSession
from app.repositories.bot import BotRepository
from app.repositories.strategy import StrategyRepository
from app.schemas.bot import BotCreate, BotRead, BotUpdate
from app.schemas.bot_dashboard import BotDashboardRead
from app.schemas.bot_summary import BotSummaryRead
from app.services.bot import BotService

router = APIRouter()


def get_bot_service(db: DbSession) -> BotService:
    return BotService(BotRepository(db), StrategyRepository(db))


@router.post("", response_model=BotRead, status_code=status.HTTP_201_CREATED)
async def create_bot(payload: BotCreate, db: DbSession) -> BotRead:
    service = get_bot_service(db)
    bot = service.create(payload)
    return BotRead.model_validate(bot)


@router.get("", response_model=BotDashboardRead)
async def list_bots(
    bot_runner: BotRunnerDep,
) -> BotDashboardRead:
    return bot_runner.list_bot_dashboard()


@router.get("/{bot_id}/summary", response_model=BotSummaryRead)
async def get_bot_summary(bot_id: int, bot_runner: BotRunnerDep) -> BotSummaryRead:
    return bot_runner.get_bot_summary(bot_id)


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
