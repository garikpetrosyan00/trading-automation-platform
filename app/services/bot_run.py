from datetime import datetime, timezone

from app.core.errors import ConflictError, NotFoundError
from app.models.bot_run import BotRun
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.execution_profile import ExecutionProfileRepository
from app.schemas.bot_run import BotRunCreate, BotRunUpdate

NON_TERMINAL_STATUSES = {"requested", "running"}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
ALLOWED_TRANSITIONS = {
    "requested": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


class BotRunService:
    def __init__(
        self,
        repository: BotRunRepository,
        bot_repository: BotRepository,
        execution_profile_repository: ExecutionProfileRepository,
    ):
        self.repository = repository
        self.bot_repository = bot_repository
        self.execution_profile_repository = execution_profile_repository

    def create(self, bot_id: int, payload: BotRunCreate) -> BotRun:
        bot = self._get_bot(bot_id)
        self._ensure_execution_profile_exists(bot_id)
        self._ensure_bot_is_active(bot.status, bot_id)

        if self.repository.get_active_for_bot(bot_id) is not None:
            raise ConflictError(
                f"Bot with id {bot_id} already has a run in progress",
                error_code="bot_run_in_progress",
            )

        bot_run = BotRun(
            bot_id=bot_id,
            trigger_type=payload.trigger_type,
            status="requested",
        )
        return self.repository.create(bot_run)

    def get_by_id_for_bot(self, bot_id: int, run_id: int) -> BotRun:
        self._ensure_bot_exists(bot_id)
        bot_run = self.repository.get_by_id_for_bot(bot_id, run_id)
        if bot_run is None:
            raise NotFoundError(
                f"Bot run with id {run_id} was not found for bot with id {bot_id}",
                error_code="bot_run_not_found",
            )
        return bot_run

    def list_for_bot(self, bot_id: int, status: str | None = None, trigger_type: str | None = None) -> list[BotRun]:
        self._ensure_bot_exists(bot_id)
        return self.repository.list_for_bot(bot_id, status=status, trigger_type=trigger_type)

    def update(self, bot_id: int, run_id: int, payload: BotRunUpdate) -> BotRun:
        bot_run = self.get_by_id_for_bot(bot_id, run_id)
        updates = payload.model_dump(exclude_unset=True)

        next_status = updates.get("status")
        if next_status is not None and next_status != bot_run.status:
            self._validate_transition(bot_run.status, next_status, bot_id)
            self._apply_status_timestamps(bot_run, next_status)

        for field, value in updates.items():
            setattr(bot_run, field, value)

        return self.repository.update(bot_run)

    def _ensure_bot_exists(self, bot_id: int) -> None:
        self._get_bot(bot_id)

    def _get_bot(self, bot_id: int):
        bot = self.bot_repository.get_by_id(bot_id)
        if bot is None:
            raise NotFoundError(
                f"Bot with id {bot_id} was not found",
                error_code="bot_not_found",
            )
        return bot

    def _ensure_execution_profile_exists(self, bot_id: int) -> None:
        if self.execution_profile_repository.get_by_bot_id(bot_id) is None:
            raise NotFoundError(
                f"Execution profile for bot with id {bot_id} was not found",
                error_code="execution_profile_not_found",
            )

    def _ensure_bot_is_active(self, bot_status: str, bot_id: int) -> None:
        if bot_status != "active":
            raise ConflictError(
                f"Bot with id {bot_id} must be active before runs can be created",
                error_code="bot_not_active",
            )

    def _validate_transition(self, current_status: str, next_status: str, bot_id: int) -> None:
        if next_status not in ALLOWED_TRANSITIONS[current_status]:
            raise ConflictError(
                f"Invalid bot run state transition from {current_status} to {next_status} for bot with id {bot_id}",
                error_code="invalid_bot_run_transition",
            )

    def _apply_status_timestamps(self, bot_run: BotRun, next_status: str) -> None:
        now = datetime.now(timezone.utc)
        if next_status == "running" and bot_run.started_at is None:
            bot_run.started_at = now
        if next_status in TERMINAL_STATUSES and bot_run.finished_at is None:
            if bot_run.started_at is None and bot_run.status == "running":
                bot_run.started_at = now
            bot_run.finished_at = now
