from fastapi import APIRouter, Response, status

from app.api.dependencies import DbSession
from app.repositories.bot import BotRepository
from app.repositories.execution_profile import ExecutionProfileRepository
from app.schemas.execution_profile import ExecutionProfileCreate, ExecutionProfileRead, ExecutionProfileUpdate
from app.services.execution_profile import ExecutionProfileService

router = APIRouter()


def get_execution_profile_service(db: DbSession) -> ExecutionProfileService:
    return ExecutionProfileService(ExecutionProfileRepository(db), BotRepository(db))


@router.post("/execution-profile", response_model=ExecutionProfileRead, status_code=status.HTTP_201_CREATED)
async def create_execution_profile(
    bot_id: int,
    payload: ExecutionProfileCreate,
    db: DbSession,
) -> ExecutionProfileRead:
    service = get_execution_profile_service(db)
    execution_profile = service.create(bot_id, payload)
    return ExecutionProfileRead.model_validate(execution_profile)


@router.get("/execution-profile", response_model=ExecutionProfileRead)
async def get_execution_profile(bot_id: int, db: DbSession) -> ExecutionProfileRead:
    service = get_execution_profile_service(db)
    execution_profile = service.get_by_bot_id(bot_id)
    return ExecutionProfileRead.model_validate(execution_profile)


@router.patch("/execution-profile", response_model=ExecutionProfileRead)
async def update_execution_profile(
    bot_id: int,
    payload: ExecutionProfileUpdate,
    db: DbSession,
) -> ExecutionProfileRead:
    service = get_execution_profile_service(db)
    execution_profile = service.update(bot_id, payload)
    return ExecutionProfileRead.model_validate(execution_profile)


@router.delete("/execution-profile", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution_profile(bot_id: int, db: DbSession) -> Response:
    service = get_execution_profile_service(db)
    service.delete(bot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
