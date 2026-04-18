from fastapi import APIRouter, Response, status

from app.api.dependencies import DbSession
from app.repositories.strategy import StrategyRepository
from app.schemas.strategy import StrategyCreate, StrategyRead, StrategyUpdate
from app.services.strategy import StrategyService

router = APIRouter()


def get_strategy_service(db: DbSession) -> StrategyService:
    return StrategyService(StrategyRepository(db))


@router.post("", response_model=StrategyRead, status_code=status.HTTP_201_CREATED)
async def create_strategy(payload: StrategyCreate, db: DbSession) -> StrategyRead:
    service = get_strategy_service(db)
    strategy = service.create(payload)
    return StrategyRead.model_validate(strategy)


@router.get("", response_model=list[StrategyRead])
async def list_strategies(db: DbSession) -> list[StrategyRead]:
    service = get_strategy_service(db)
    strategies = service.list_all()
    return [StrategyRead.model_validate(strategy) for strategy in strategies]


@router.get("/{strategy_id}", response_model=StrategyRead)
async def get_strategy(strategy_id: int, db: DbSession) -> StrategyRead:
    service = get_strategy_service(db)
    strategy = service.get_by_id(strategy_id)
    return StrategyRead.model_validate(strategy)


@router.patch("/{strategy_id}", response_model=StrategyRead)
async def update_strategy(strategy_id: int, payload: StrategyUpdate, db: DbSession) -> StrategyRead:
    service = get_strategy_service(db)
    strategy = service.update(strategy_id, payload)
    return StrategyRead.model_validate(strategy)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(strategy_id: int, db: DbSession) -> Response:
    service = get_strategy_service(db)
    service.delete(strategy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
