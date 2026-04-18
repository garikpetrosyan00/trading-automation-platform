from app.core.errors import ConflictError, NotFoundError
from app.models.execution_profile import ExecutionProfile
from app.repositories.bot import BotRepository
from app.repositories.execution_profile import ExecutionProfileRepository
from app.schemas.execution_profile import ExecutionProfileCreate, ExecutionProfileUpdate


class ExecutionProfileService:
    def __init__(self, repository: ExecutionProfileRepository, bot_repository: BotRepository):
        self.repository = repository
        self.bot_repository = bot_repository

    def create(self, bot_id: int, payload: ExecutionProfileCreate) -> ExecutionProfile:
        self._ensure_bot_exists(bot_id)
        if self.repository.get_by_bot_id(bot_id) is not None:
            raise ConflictError(
                f"Execution profile already exists for bot with id {bot_id}",
                error_code="execution_profile_exists",
            )

        execution_profile = ExecutionProfile(bot_id=bot_id, **payload.model_dump())
        return self.repository.create(execution_profile)

    def get_by_bot_id(self, bot_id: int) -> ExecutionProfile:
        self._ensure_bot_exists(bot_id)
        execution_profile = self.repository.get_by_bot_id(bot_id)
        if execution_profile is None:
            raise NotFoundError(
                f"Execution profile for bot with id {bot_id} was not found",
                error_code="execution_profile_not_found",
            )
        return execution_profile

    def update(self, bot_id: int, payload: ExecutionProfileUpdate) -> ExecutionProfile:
        execution_profile = self.get_by_bot_id(bot_id)
        updates = payload.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(execution_profile, field, value)

        return self.repository.update(execution_profile)

    def delete(self, bot_id: int) -> None:
        execution_profile = self.get_by_bot_id(bot_id)
        self.repository.delete(execution_profile)

    def _ensure_bot_exists(self, bot_id: int) -> None:
        if self.bot_repository.get_by_id(bot_id) is None:
            raise NotFoundError(
                f"Bot with id {bot_id} was not found",
                error_code="bot_not_found",
            )
