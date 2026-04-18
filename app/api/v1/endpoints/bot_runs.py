from fastapi import APIRouter, Query, status

from app.api.dependencies import DbSession
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.execution_profile import ExecutionProfileRepository
from app.repositories.run_event import RunEventRepository
from app.schemas.bot_run import BotRunCreate, BotRunRead, BotRunStatus, BotRunTriggerType, BotRunUpdate
from app.services.bot_run import BotRunService

router = APIRouter()


def get_bot_run_service(db: DbSession) -> BotRunService:
    return BotRunService(
        BotRunRepository(db),
        BotRepository(db),
        ExecutionProfileRepository(db),
        RunEventRepository(db),
    )


@router.post("/runs", response_model=BotRunRead, status_code=status.HTTP_201_CREATED)
async def create_bot_run(bot_id: int, payload: BotRunCreate, db: DbSession) -> BotRunRead:
    service = get_bot_run_service(db)
    bot_run = service.create(bot_id, payload)
    return BotRunRead.model_validate(bot_run)


@router.get("/runs", response_model=list[BotRunRead])
async def list_bot_runs(
    bot_id: int,
    db: DbSession,
    status: BotRunStatus | None = Query(default=None),
    trigger_type: BotRunTriggerType | None = Query(default=None),
) -> list[BotRunRead]:
    service = get_bot_run_service(db)
    bot_runs = service.list_for_bot(bot_id, status=status, trigger_type=trigger_type)
    return [BotRunRead.model_validate(bot_run) for bot_run in bot_runs]


@router.get("/runs/{run_id}", response_model=BotRunRead)
async def get_bot_run(bot_id: int, run_id: int, db: DbSession) -> BotRunRead:
    service = get_bot_run_service(db)
    bot_run = service.get_by_id_for_bot(bot_id, run_id)
    return BotRunRead.model_validate(bot_run)


@router.patch("/runs/{run_id}", response_model=BotRunRead)
async def update_bot_run(bot_id: int, run_id: int, payload: BotRunUpdate, db: DbSession) -> BotRunRead:
    service = get_bot_run_service(db)
    bot_run = service.update(bot_id, run_id, payload)
    return BotRunRead.model_validate(bot_run)
