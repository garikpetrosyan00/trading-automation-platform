from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder

from app.core.errors import NotFoundError
from app.models.alert_event import AlertEvent
from app.models.bot_run import BotRun
from app.models.run_event import RunEvent
from app.repositories.alert_event import AlertEventRepository
from app.repositories.alert_rule import AlertRuleRepository
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.run_event import RunEventRepository


class AlertEventService:
    def __init__(
        self,
        repository: AlertEventRepository,
        bot_repository: BotRepository,
        bot_run_repository: BotRunRepository,
        alert_rule_repository: AlertRuleRepository,
        run_event_repository: RunEventRepository,
    ):
        self.repository = repository
        self.bot_repository = bot_repository
        self.bot_run_repository = bot_run_repository
        self.alert_rule_repository = alert_rule_repository
        self.run_event_repository = run_event_repository

    def evaluate_alerts_for_bot(
        self,
        bot_id: int,
        bot_run_id: int | None = None,
        force: bool = False,
    ) -> dict:
        self._ensure_bot_exists(bot_id)
        bot_run = self._get_bot_run_for_bot(bot_id, bot_run_id) if bot_run_id is not None else None
        context = self._build_runtime_context(bot_run)
        alert_rules = self.alert_rule_repository.list_enabled_for_bot(bot_id)

        triggered_events: list[AlertEvent] = []
        evaluated_rules_count = 0

        for alert_rule in alert_rules:
            evaluated_rules_count += 1
            actual_value = self._resolve_context_value(context, alert_rule.field_name)
            if actual_value is None:
                continue

            if not self._matches(alert_rule.operator, alert_rule.threshold_value, actual_value):
                continue

            if not force and self._is_in_cooldown(alert_rule.id, alert_rule.cooldown_seconds):
                continue

            triggered_events.append(self._create_alert_event(bot_id, bot_run, alert_rule, actual_value))

        return {
            "bot_id": bot_id,
            "bot_run_id": bot_run.id if bot_run is not None else None,
            "evaluated_rules_count": evaluated_rules_count,
            "triggered_events": triggered_events,
        }

    def list_alert_events_for_bot(
        self,
        bot_id: int,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AlertEvent]:
        self._ensure_bot_exists(bot_id)
        return self.repository.list_for_bot(bot_id, limit=limit, offset=offset)

    def list_alert_events_for_rule(self, alert_rule_id: int) -> list[AlertEvent]:
        self._ensure_alert_rule_exists(alert_rule_id)
        return self.repository.list_for_rule(alert_rule_id)

    def get_alert_event(self, alert_event_id: int) -> AlertEvent:
        alert_event = self.repository.get_by_id(alert_event_id)
        if alert_event is None:
            raise NotFoundError(
                f"Alert event with id {alert_event_id} was not found",
                error_code="alert_event_not_found",
            )
        return alert_event

    def _ensure_bot_exists(self, bot_id: int) -> None:
        if self.bot_repository.get_by_id(bot_id) is None:
            raise NotFoundError(
                f"Bot with id {bot_id} was not found",
                error_code="bot_not_found",
            )

    def _ensure_alert_rule_exists(self, alert_rule_id: int) -> None:
        if self.alert_rule_repository.get_by_id(alert_rule_id) is None:
            raise NotFoundError(
                f"Alert rule with id {alert_rule_id} was not found",
                error_code="alert_rule_not_found",
            )

    def _get_bot_run_for_bot(self, bot_id: int, bot_run_id: int) -> BotRun:
        bot_run = self.bot_run_repository.get_by_id(bot_run_id)
        if bot_run is None:
            raise NotFoundError(
                f"Bot run with id {bot_run_id} was not found",
                error_code="bot_run_not_found",
            )
        if bot_run.bot_id != bot_id:
            raise NotFoundError(
                f"Bot run with id {bot_run_id} does not belong to bot with id {bot_id}",
                error_code="bot_run_mismatch",
            )
        return bot_run

    def _build_runtime_context(self, bot_run: BotRun | None) -> dict[str, object]:
        context: dict[str, object] = {}
        if bot_run is None:
            return context

        context["status"] = bot_run.status
        context["started_at"] = bot_run.started_at.isoformat() if bot_run.started_at is not None else None
        context["finished_at"] = bot_run.finished_at.isoformat() if bot_run.finished_at is not None else None
        context["error_message"] = bot_run.error_message

        if bot_run.started_at is not None and bot_run.finished_at is not None:
            duration = bot_run.finished_at - bot_run.started_at
            context["duration_seconds"] = duration.total_seconds()

        run_events = self.run_event_repository.list_for_run(bot_run.id)
        if run_events:
            context.update(self._build_run_event_context(run_events))

        return context

    def _build_run_event_context(self, run_events: list[RunEvent]) -> dict[str, object]:
        error_count = 0
        warning_count = 0
        info_count = 0

        for run_event in run_events:
            if run_event.level == "error":
                error_count += 1
            elif run_event.level == "warning":
                warning_count += 1
            elif run_event.level == "info":
                info_count += 1

        last_event = run_events[-1]
        return {
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "last_event_level": last_event.level,
            "total_events_count": len(run_events),
        }

    def _resolve_context_value(self, context: dict[str, object], field_name: str) -> object | None:
        if field_name not in context:
            return None
        return context[field_name]

    def _matches(self, operator: str, threshold_value: str, actual_value: object) -> bool:
        if operator == "contains":
            return isinstance(actual_value, str) and threshold_value in actual_value

        numeric_actual = self._to_number(actual_value)
        numeric_threshold = self._to_number(threshold_value)

        if operator == "gt":
            return numeric_actual is not None and numeric_threshold is not None and numeric_actual > numeric_threshold
        if operator == "gte":
            return numeric_actual is not None and numeric_threshold is not None and numeric_actual >= numeric_threshold
        if operator == "lt":
            return numeric_actual is not None and numeric_threshold is not None and numeric_actual < numeric_threshold
        if operator == "lte":
            return numeric_actual is not None and numeric_threshold is not None and numeric_actual <= numeric_threshold
        if operator == "eq":
            if numeric_actual is not None and numeric_threshold is not None:
                return numeric_actual == numeric_threshold
            return str(actual_value) == threshold_value
        if operator == "neq":
            if numeric_actual is not None and numeric_threshold is not None:
                return numeric_actual != numeric_threshold
            return str(actual_value) != threshold_value

        return False

    def _to_number(self, value: object) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _is_in_cooldown(self, alert_rule_id: int, cooldown_seconds: int) -> bool:
        if cooldown_seconds <= 0:
            return False

        latest_event = self.repository.get_latest_triggered_for_rule(alert_rule_id)
        if latest_event is None:
            return False

        now = datetime.now(timezone.utc)
        elapsed = now - latest_event.triggered_at
        return elapsed.total_seconds() < cooldown_seconds

    def _create_alert_event(self, bot_id: int, bot_run: BotRun | None, alert_rule, actual_value: object) -> AlertEvent:
        now = datetime.now(timezone.utc)
        actual_value_str = self._stringify_value(actual_value)
        title = self._build_title(alert_rule.field_name, alert_rule.operator)
        message = self._build_message(
            field_name=alert_rule.field_name,
            operator=alert_rule.operator,
            threshold_value=alert_rule.threshold_value,
            actual_value=actual_value_str,
            bot_run_id=bot_run.id if bot_run is not None else None,
        )

        alert_event = AlertEvent(
            bot_id=bot_id,
            bot_run_id=bot_run.id if bot_run is not None else None,
            alert_rule_id=alert_rule.id,
            status="triggered",
            severity=alert_rule.severity,
            field_name=alert_rule.field_name,
            operator=alert_rule.operator,
            threshold_value=alert_rule.threshold_value,
            actual_value=actual_value_str,
            title=title,
            message=message,
            dedup_key=f"alert-rule:{alert_rule.id}",
            triggered_at=now,
        )
        alert_event = self.repository.create(alert_event)

        alert_rule.last_triggered_at = now
        self.alert_rule_repository.update(alert_rule)
        return alert_event

    def _build_title(self, field_name: str, operator: str) -> str:
        if operator in {"gt", "gte", "lt", "lte"}:
            return f"{field_name} crossed rule threshold"
        return f"{field_name} matched alert condition"

    def _build_message(
        self,
        field_name: str,
        operator: str,
        threshold_value: str,
        actual_value: str | None,
        bot_run_id: int | None,
    ) -> str:
        message = (
            f"Alert triggered for field {field_name} with operator {operator}, "
            f"threshold {threshold_value}, actual value {actual_value}."
        )
        if bot_run_id is not None:
            message = f"{message} bot_run_id={bot_run_id}."
        return message

    def _stringify_value(self, value: object) -> str | None:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        encoded_value = jsonable_encoder(value)
        return str(encoded_value)
