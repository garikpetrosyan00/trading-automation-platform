from typing import Any

from app.core.errors import AppError, NotFoundError
from app.models.strategy import Strategy
from app.repositories.strategy import StrategyRepository
from app.schemas.strategy import (
    StrategyCreate,
    StrategyUpdate,
    validate_moving_average_cross_parameters,
    validate_price_threshold_parameters,
    validate_rsi_threshold_parameters,
)


def validate_strategy_parameters(strategy_type: str, parameters: dict[str, Any] | None) -> None:
    try:
        if strategy_type == "price_threshold":
            validate_price_threshold_parameters(parameters)
        elif strategy_type == "moving_average_cross":
            validate_moving_average_cross_parameters(parameters)
        elif strategy_type == "rsi_threshold":
            validate_rsi_threshold_parameters(parameters)
    except ValueError as exc:
        raise AppError(str(exc), status_code=422, error_code="invalid_strategy_parameters") from exc


class StrategyService:
    def __init__(self, repository: StrategyRepository):
        self.repository = repository

    def create(self, payload: StrategyCreate) -> Strategy:
        validate_strategy_parameters(payload.strategy_type, payload.parameters)
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
        strategy_type = updates.get("strategy_type", strategy.strategy_type or "price_threshold")
        if "parameters" in updates:
            validate_strategy_parameters(strategy_type, updates["parameters"])
        elif "strategy_type" in updates:
            validate_strategy_parameters(strategy_type, strategy.parameters)

        for field, value in updates.items():
            setattr(strategy, field, value)

        return self.repository.update(strategy)

    def delete(self, strategy_id: int) -> None:
        strategy = self.get_by_id(strategy_id)
        self.repository.delete(strategy)
