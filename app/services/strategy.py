from app.core.errors import NotFoundError
from app.models.strategy import Strategy
from app.repositories.strategy import StrategyRepository
from app.schemas.strategy import StrategyCreate, StrategyUpdate


class StrategyService:
    def __init__(self, repository: StrategyRepository):
        self.repository = repository

    def create(self, payload: StrategyCreate) -> Strategy:
        strategy = Strategy(**payload.model_dump())
        return self.repository.create(strategy)

    def get_by_id(self, strategy_id: int) -> Strategy:
        strategy = self.repository.get_by_id(strategy_id)
        if strategy is None:
            raise NotFoundError(f"Strategy with id {strategy_id} was not found", error_code="strategy_not_found")
        return strategy

    def list_all(self) -> list[Strategy]:
        return self.repository.list_all()

    def update(self, strategy_id: int, payload: StrategyUpdate) -> Strategy:
        strategy = self.get_by_id(strategy_id)
        updates = payload.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(strategy, field, value)

        return self.repository.update(strategy)

    def delete(self, strategy_id: int) -> None:
        strategy = self.get_by_id(strategy_id)
        self.repository.delete(strategy)
