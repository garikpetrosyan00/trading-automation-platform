from fastapi import APIRouter, Query, status

from app.api.dependencies import DbSession
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.run_event import RunEventRepository
from app.schemas.run_event import RunEventCreate, RunEventLevel, RunEventRead, RunEventType
from app.services.run_event import RunEventService

router = APIRouter()


def get_run_event_service(db: DbSession) -> RunEventService:
    return RunEventService(
        RunEventRepository(db),
        BotRepository(db),
        BotRunRepository(db),
    )


@router.post("/events", response_model=RunEventRead, status_code=status.HTTP_201_CREATED)
async def create_run_event(bot_id: int, run_id: int, payload: RunEventCreate, db: DbSession) -> RunEventRead:
    service = get_run_event_service(db)
    run_event = service.create(bot_id, run_id, payload)
    return RunEventRead.model_validate(run_event)


@router.get("/events", response_model=list[RunEventRead])
async def list_run_events(
    bot_id: int,
    run_id: int,
    db: DbSession,
    event_type: RunEventType | None = Query(default=None),
    level: RunEventLevel | None = Query(default=None),
) -> list[RunEventRead]:
    service = get_run_event_service(db)
    run_events = service.list_for_run(bot_id, run_id, event_type=event_type, level=level)
    return [RunEventRead.model_validate(run_event) for run_event in run_events]


@router.get("/events/{event_id}", response_model=RunEventRead)
async def get_run_event(bot_id: int, run_id: int, event_id: int, db: DbSession) -> RunEventRead:
    service = get_run_event_service(db)
    run_event = service.get_by_id_for_run(bot_id, run_id, event_id)
    return RunEventRead.model_validate(run_event)
