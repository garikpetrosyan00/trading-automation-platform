from app.core.errors import NotFoundError
from app.models.bot import Bot
from app.repositories.bot import BotRepository
from app.repositories.strategy import StrategyRepository
from app.schemas.bot import BotCreate, BotUpdate


class BotService:
    def __init__(self, repository: BotRepository, strategy_repository: StrategyRepository):
        self.repository = repository
        self.strategy_repository = strategy_repository

    def create(self, payload: BotCreate) -> Bot:
        self._ensure_strategy_exists(payload.strategy_id)
        bot = Bot(**payload.model_dump())
        return self.repository.create(bot)

    def get_by_id(self, bot_id: int) -> Bot:
        bot = self.repository.get_by_id(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")
        return bot

    def list_all(self, strategy_id: int | None = None, status: str | None = None) -> list[Bot]:
        return self.repository.list_all(strategy_id=strategy_id, status=status)

    def update(self, bot_id: int, payload: BotUpdate) -> Bot:
        bot = self.get_by_id(bot_id)
        updates = payload.model_dump(exclude_unset=True)

        if "strategy_id" in updates:
            self._ensure_strategy_exists(updates["strategy_id"])

        for field, value in updates.items():
            setattr(bot, field, value)

        return self.repository.update(bot)

    def delete(self, bot_id: int) -> None:
        bot = self.get_by_id(bot_id)
        self.repository.delete(bot)

    def _ensure_strategy_exists(self, strategy_id: int) -> None:
        if self.strategy_repository.get_by_id(strategy_id) is None:
            raise NotFoundError(
                f"Strategy with id {strategy_id} was not found",
                error_code="strategy_not_found",
            )
