from app.core.errors import NotFoundError
from app.models.run_event import RunEvent
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.run_event import RunEventRepository
from app.schemas.run_event import RunEventCreate


class RunEventService:
    def __init__(
        self,
        repository: RunEventRepository,
        bot_repository: BotRepository,
        bot_run_repository: BotRunRepository,
    ):
        self.repository = repository
        self.bot_repository = bot_repository
        self.bot_run_repository = bot_run_repository

    def create(self, bot_id: int, run_id: int, payload: RunEventCreate) -> RunEvent:
        bot_run = self._get_run_for_bot(bot_id, run_id)
        run_event = RunEvent(bot_run_id=bot_run.id, **payload.model_dump())
        return self.repository.create(run_event)

    def list_for_run(self, bot_id: int, run_id: int, event_type: str | None = None, level: str | None = None) -> list[RunEvent]:
        bot_run = self._get_run_for_bot(bot_id, run_id)
        return self.repository.list_for_run(bot_run.id, event_type=event_type, level=level)

    def get_by_id_for_run(self, bot_id: int, run_id: int, event_id: int) -> RunEvent:
        bot_run = self._get_run_for_bot(bot_id, run_id)
        run_event = self.repository.get_by_id_for_run(bot_run.id, event_id)
        if run_event is None:
            raise NotFoundError(
                f"Run event with id {event_id} was not found for bot run with id {run_id}",
                error_code="run_event_not_found",
            )
        return run_event

    def _get_run_for_bot(self, bot_id: int, run_id: int):
        if self.bot_repository.get_by_id(bot_id) is None:
            raise NotFoundError(
                f"Bot with id {bot_id} was not found",
                error_code="bot_not_found",
            )

        bot_run = self.bot_run_repository.get_by_id(run_id)
        if bot_run is None:
            raise NotFoundError(
                f"Bot run with id {run_id} was not found",
                error_code="bot_run_not_found",
            )
        if bot_run.bot_id != bot_id:
            raise NotFoundError(
                f"Bot run with id {run_id} does not belong to bot with id {bot_id}",
                error_code="bot_run_mismatch",
            )
        return bot_run
