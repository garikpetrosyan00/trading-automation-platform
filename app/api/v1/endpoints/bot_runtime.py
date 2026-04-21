from fastapi import APIRouter, Query, status

from app.api.dependencies import BotRunnerDep, DbSession
from app.core.errors import NotFoundError
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.execution_profile import ExecutionProfileRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.schemas.bot_activity import BotActivityRead, build_activity_item
from app.schemas.bot_manual_run import BotManualRunRead
from app.schemas.bot_run import BotRunRead, BotRunStatus, BotRunTriggerType
from app.schemas.bot_runner import BotControlRead, BotStatusRead
from app.schemas.run_event import RunEventLevel, RunEventRead, RunEventType
from app.services.bot_run import BotRunService
from app.services.run_event import RunEventService

router = APIRouter()


def get_bot_run_service(db: DbSession) -> BotRunService:
    return BotRunService(
        BotRunRepository(db),
        BotRepository(db),
        ExecutionProfileRepository(db),
        RunEventRepository(db),
    )


def get_run_event_service(db: DbSession) -> RunEventService:
    return RunEventService(
        RunEventRepository(db),
        BotRepository(db),
        BotRunRepository(db),
    )


@router.post("/bots/{bot_id}/start", response_model=BotStatusRead, status_code=status.HTTP_200_OK)
async def start_bot(bot_id: int, bot_runner: BotRunnerDep) -> BotStatusRead:
    return bot_runner.start_bot(bot_id)


@router.post("/bots/{bot_id}/stop", response_model=BotStatusRead, status_code=status.HTTP_200_OK)
async def stop_bot(bot_id: int, bot_runner: BotRunnerDep) -> BotStatusRead:
    return bot_runner.stop_bot(bot_id)


@router.post("/bots/{bot_id}/pause", response_model=BotControlRead, status_code=status.HTTP_200_OK)
async def pause_bot(bot_id: int, bot_runner: BotRunnerDep) -> BotControlRead:
    return bot_runner.pause_bot(bot_id)


@router.post("/bots/{bot_id}/resume", response_model=BotControlRead, status_code=status.HTTP_200_OK)
async def resume_bot(bot_id: int, bot_runner: BotRunnerDep) -> BotControlRead:
    return bot_runner.resume_bot(bot_id)


@router.post("/bots/{bot_id}/run", response_model=BotManualRunRead, status_code=status.HTTP_200_OK)
async def run_bot_once(bot_id: int, bot_runner: BotRunnerDep) -> BotManualRunRead:
    return await bot_runner.run_bot_once(bot_id)


@router.get("/bots/{bot_id}/status", response_model=BotStatusRead)
async def get_bot_status(bot_id: int, bot_runner: BotRunnerDep) -> BotStatusRead:
    return bot_runner.get_bot_status(bot_id)


@router.get("/bots/{bot_id}/activity", response_model=BotActivityRead)
async def get_bot_activity(
    bot_id: int,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> BotActivityRead:
    if BotRepository(db).get_by_id(bot_id) is None:
        raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

    portfolio_repository = PortfolioRepository(db)
    run_events = RunEventRepository(db).list_recent_for_bot(bot_id, limit=limit)
    items = []
    for run_event in run_events:
        items.append(build_activity_item(run_event, portfolio_repository))
    return BotActivityRead(bot_id=bot_id, items=items)


@router.get("/bot-runs", response_model=list[BotRunRead])
async def list_bot_runs(
    db: DbSession,
    bot_id: int = Query(...),
    status: BotRunStatus | None = Query(default=None),
    trigger_type: BotRunTriggerType | None = Query(default=None),
) -> list[BotRunRead]:
    service = get_bot_run_service(db)
    bot_runs = service.list_for_bot(bot_id, status=status, trigger_type=trigger_type)
    return [BotRunRead.model_validate(bot_run) for bot_run in bot_runs]


@router.get("/run-events", response_model=list[RunEventRead])
async def list_run_events(
    db: DbSession,
    bot_id: int = Query(...),
    run_id: int | None = Query(default=None),
    event_type: RunEventType | None = Query(default=None),
    level: RunEventLevel | None = Query(default=None),
) -> list[RunEventRead]:
    service = get_run_event_service(db)
    run_events = service.list_for_bot(bot_id, run_id=run_id, event_type=event_type, level=level)
    return [RunEventRead.model_validate(run_event) for run_event in run_events]
