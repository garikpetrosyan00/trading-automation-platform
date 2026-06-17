import argparse
import json
import sys
from typing import Callable, TextIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.engine.bot_runner import BotRunner, RunnerConfig
from app.models.execution_attempt import ExecutionAttempt
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.bot import BotRepository


class CliArgumentError(Exception):
    pass


class CliRuntimeError(Exception):
    pass


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(message)


RunnerFactory = Callable[[Callable[[], Session]], BotRunner]
SessionFactory = Callable[[], Session]


def build_runner(
    session_factory: SessionFactory,
    *,
    settings_provider: Callable[[], Settings] = get_settings,
) -> BotRunner:
    from app.services.market_data_service import MarketDataService

    settings = settings_provider()
    market_data_service = MarketDataService.from_settings(settings)
    return BotRunner(
        session_factory=session_factory,
        market_data_service=market_data_service,
        config=RunnerConfig(
            enabled=True,
            poll_interval_seconds=settings.bot_runner_poll_interval_seconds,
            simulation_enabled=settings.simulation_enabled,
            simulation_fee_bps=settings.simulation_fee_bps,
            simulation_slippage_bps=settings.simulation_slippage_bps,
            execution_global_enabled=settings.execution_global_enabled,
            execution_live_enabled=False,
            binance_testnet_broker_enabled=False,
            binance_testnet_order_submission_enabled=False,
            execution_max_order_notional=settings.execution_max_order_notional,
            execution_max_daily_order_count=settings.execution_max_daily_order_count,
            execution_max_daily_loss=settings.execution_max_daily_loss,
        ),
    )


def run_once(
    *,
    bot_id: int,
    record_noop_events: bool = False,
    session_factory: SessionFactory | None = None,
    runner_factory: RunnerFactory = build_runner,
) -> dict[str, object]:
    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    with session_factory() as db:
        bot = BotRepository(db).get_by_id(bot_id)
        if bot is None:
            raise CliRuntimeError(f"bot {bot_id} was not found")

        execution_mode = _bot_execution_mode(bot)
        if execution_mode != "paper" or not bot.is_paper:
            raise CliRuntimeError(f"bot {bot_id} is not a paper bot")

        status_before = bot.status
        before = _artifact_counts(db, bot_id)
        runner = runner_factory(session_factory)
        runner._evaluate_bot(db, bot_id, record_noop_events=record_noop_events)
        db.expire_all()
        bot_after = BotRepository(db).get_by_id(bot_id)
        after = _artifact_counts(db, bot_id)

    orders_created = after["paper_orders"] - before["paper_orders"]
    fills_created = after["paper_fills"] - before["paper_fills"]
    attempts_created = after["execution_attempts"] - before["execution_attempts"]
    executed = orders_created > 0 or fills_created > 0 or attempts_created > 0

    return {
        "bot_id": bot_id,
        "execution_mode": execution_mode,
        "status": bot_after.status if bot_after is not None else status_before,
        "result": _result_for(status_before=status_before, executed=executed),
        "action": _action_for(
            status_before=status_before,
            orders_created=orders_created,
            fills_created=fills_created,
            attempts_created=attempts_created,
        ),
        "skipped": not executed,
        "executed": executed,
        "record_noop_events": record_noop_events,
        "paper_orders_created": orders_created,
        "paper_fills_created": fills_created,
        "execution_attempts_created": attempts_created,
    }


def main(
    argv: list[str] | None = None,
    *,
    session_factory: SessionFactory | None = None,
    runner_factory: RunnerFactory = build_runner,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        summary = run_once(
            bot_id=args.bot_id,
            record_noop_events=args.record_noop_events,
            session_factory=session_factory,
            runner_factory=runner_factory,
        )
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except CliRuntimeError as exc:
        print(f"error: {exc}", file=stderr)
        return 1
    except Exception:
        print("error: one-shot bot runner command failed", file=stderr)
        return 1

    print(json.dumps(summary, sort_keys=True), file=stdout)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="run-bot-runner-once",
        description="Evaluate exactly one paper bot through the runner path and exit.",
    )
    parser.add_argument("--bot-id", type=_positive_int, required=True, help="paper bot id to evaluate once")
    parser.add_argument(
        "--record-noop-events",
        action="store_true",
        help="record runner no-op events when supported by the existing runner path",
    )
    return parser


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bot id must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("bot id must be greater than zero")
    return parsed


def _artifact_counts(db: Session, bot_id: int) -> dict[str, int]:
    order_count = int(
        db.scalar(
            select(func.count())
            .select_from(SimulatedOrder)
            .where(SimulatedOrder.bot_id == bot_id, SimulatedOrder.mode == "paper")
        )
        or 0
    )
    fill_count = int(
        db.scalar(
            select(func.count())
            .select_from(SimulatedFill)
            .join(SimulatedOrder, SimulatedOrder.id == SimulatedFill.order_id)
            .where(SimulatedOrder.bot_id == bot_id, SimulatedOrder.mode == "paper")
        )
        or 0
    )
    attempt_count = int(
        db.scalar(
            select(func.count())
            .select_from(ExecutionAttempt)
            .where(ExecutionAttempt.bot_id == bot_id, ExecutionAttempt.mode == "paper")
        )
        or 0
    )
    return {
        "paper_orders": order_count,
        "paper_fills": fill_count,
        "execution_attempts": attempt_count,
    }


def _action_for(
    *,
    status_before: str,
    orders_created: int,
    fills_created: int,
    attempts_created: int,
) -> str:
    if status_before == "paused":
        return "bot_paused"
    if status_before != "active":
        return "bot_not_active"
    if orders_created > 0 or fills_created > 0:
        return "paper_order_created"
    if attempts_created > 0:
        return "execution_attempt_recorded"
    return "no_order_created"


def _result_for(*, status_before: str, executed: bool) -> str:
    if executed:
        return "evaluated"
    if status_before == "active":
        return "evaluated"
    return "skipped"


def _bot_execution_mode(bot) -> str:
    return bot.execution_mode or ("paper" if bot.is_paper else "live")


if __name__ == "__main__":
    raise SystemExit(main())
