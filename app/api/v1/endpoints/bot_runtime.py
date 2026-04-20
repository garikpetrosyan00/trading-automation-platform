from fastapi import APIRouter, Query, status

from app.api.dependencies import BotRunnerDep, DbSession
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.execution_profile import ExecutionProfileRepository
from app.repositories.run_event import RunEventRepository
from app.schemas.bot_run import BotRunRead, BotRunStatus, BotRunTriggerType
from app.schemas.bot_runner import BotStatusRead
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


@router.get("/bots/{bot_id}/status", response_model=BotStatusRead)
async def get_bot_status(bot_id: int, bot_runner: BotRunnerDep) -> BotStatusRead:
    return bot_runner.get_bot_status(bot_id)


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
