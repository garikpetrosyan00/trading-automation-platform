from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.data.schemas import MarketEvent
from app.engine.risk import RISK_REASON_STOP_LOSS_TRIGGERED, RiskLimits, RiskManager
from app.engine.strategy_engine import (
    BOLLINGER_BANDS_STRATEGY_TYPE,
    MACD_CROSSOVER_STRATEGY_TYPE,
    MOVING_AVERAGE_CROSS_STRATEGY_TYPE,
    PRICE_THRESHOLD_STRATEGY_TYPE,
    RSI_THRESHOLD_STRATEGY_TYPE,
    StrategyEngine,
)
from app.models.bot_run import BotRun
from app.models.run_event import RunEvent
from app.repositories.bot import BotRepository
from app.repositories.bot_run import BotRunRepository
from app.repositories.execution_profile import ExecutionProfileRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.market_candle import MarketCandleRepository
from app.repositories.paper_accounting import PaperAccountingRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.repositories.strategy import StrategyRepository
from app.schemas.bot_activity import build_activity_item
from app.schemas.bot_dashboard import BotDashboardItemRead, BotDashboardRead
from app.schemas.bot_manual_run import BotDecisionExplanationRead, BotManualRunRead
from app.schemas.bot_run import BotRunCreate, BotRunUpdate
from app.schemas.bot_runner import BotControlRead, BotStatusRead
from app.schemas.bot_summary import BotSummaryRead
from app.services.bot_run import BotRunService
from app.services.brokers.safety import ExecutionSafetyConfig, ExecutionSafetyGuard
from app.services.execution_attempt import ExecutionAttemptService
from app.services.execution_limits import ExecutionDailyLimitService
from app.services.simulated_execution import PaperOrderIntent, SimulatedExecutionService

logger = get_logger(__name__)

ZERO = Decimal("0")


@dataclass
class RunnerConfig:
    enabled: bool
    poll_interval_seconds: float
    simulation_enabled: bool
    simulation_fee_bps: Decimal
    simulation_slippage_bps: Decimal
    execution_global_enabled: bool = True
    execution_live_enabled: bool = False
    binance_testnet_order_submission_enabled: bool = False
    execution_max_order_notional: Decimal | None = None
    execution_max_daily_order_count: int | None = None
    execution_max_daily_loss: Decimal | None = None


class BotRunner:
    def __init__(
        self,
        session_factory,
        market_data_service,
        config: RunnerConfig,
        now_provider=None,
        risk_manager: RiskManager | None = None,
    ):
        self.session_factory = session_factory
        self.market_data_service = market_data_service
        self.config = config
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.risk_manager = risk_manager or RiskManager()
        self._risk_manager_override = risk_manager is not None
        self._task: asyncio.Task[None] | None = None
        self._cycle_lock = asyncio.Lock()

    async def start(self) -> None:
        if not self.config.enabled:
            logger.info("bot_runner_disabled")
            return
        if self._task is not None and not self._task.done():
            return
        logger.info("bot_runner_starting")
        self._task = asyncio.create_task(self._run_loop(), name="bot-runner")

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        logger.info("bot_runner_stopping")
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        self._cancel_active_runs("Bot runner stopped")

    async def run_cycle(self) -> None:
        async with self._cycle_lock:
            self._run_cycle_sync()

    async def run_bot_once(self, bot_id: int) -> BotManualRunRead:
        async with self._cycle_lock:
            return self._run_bot_once_sync(bot_id)

    def start_bot(self, bot_id: int) -> BotStatusRead:
        with self.session_factory() as db:
            bot_repository = BotRepository(db)
            bot = bot_repository.get_by_id(bot_id)
            if bot is None:
                raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

            profile_repository = ExecutionProfileRepository(db)
            strategy_repository = StrategyRepository(db)
            bot_run_service = self._build_bot_run_service(db)
            profile = profile_repository.get_by_bot_id(bot_id)
            if profile is None:
                raise NotFoundError(
                    f"Execution profile for bot with id {bot_id} was not found",
                    error_code="execution_profile_not_found",
                )
            strategy = strategy_repository.get_by_id(bot.strategy_id)
            if strategy is None:
                raise NotFoundError(
                    f"Strategy with id {bot.strategy_id} was not found",
                    error_code="strategy_not_found",
                )
            if bot.status != "active":
                bot.status = "active"
                bot_repository.update(bot)

            bot_run = self._ensure_running_run(bot_run_service, bot_id, trigger_type="manual")
            self._record_event(
                db,
                bot_run.id,
                event_type="lifecycle",
                level="info",
                message="started",
                payload={"symbol": strategy.symbol, "strategy_type": self._strategy_type(strategy)},
            )
            db.commit()
            return self._build_status(db, bot_id)

    def stop_bot(self, bot_id: int) -> BotStatusRead:
        with self.session_factory() as db:
            bot_repository = BotRepository(db)
            bot = bot_repository.get_by_id(bot_id)
            if bot is None:
                raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

            if bot.status != "paused":
                bot.status = "paused"
                bot_repository.update(bot)

            bot_run_repository = BotRunRepository(db)
            bot_run_service = self._build_bot_run_service(db)
            active_run = bot_run_repository.get_active_for_bot(bot_id)
            if active_run is not None:
                bot_run_service.update(
                    bot_id,
                    active_run.id,
                    BotRunUpdate(status="cancelled", summary="Bot stopped manually"),
                )
                self._record_event(
                    db,
                    active_run.id,
                    event_type="lifecycle",
                    level="info",
                    message="stopped",
                    payload={"reason": "manual_stop"},
                )
                db.commit()

            return self._build_status(db, bot_id)

    def pause_bot(self, bot_id: int) -> BotControlRead:
        with self.session_factory() as db:
            bot_repository = BotRepository(db)
            bot = bot_repository.get_by_id(bot_id)
            if bot is None:
                raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

            if bot.status != "paused":
                bot.status = "paused"
                bot_repository.update(bot)

            active_run = BotRunRepository(db).get_active_for_bot(bot_id)
            if active_run is not None:
                self._record_event(
                    db,
                    active_run.id,
                    event_type="system",
                    level="info",
                    message="bot_paused",
                    payload={"bot_status": bot.status},
                )
                db.commit()

            return BotControlRead(bot_id=bot.id, status=bot.status, is_paused=True)

    def resume_bot(self, bot_id: int) -> BotControlRead:
        with self.session_factory() as db:
            bot_repository = BotRepository(db)
            bot = bot_repository.get_by_id(bot_id)
            if bot is None:
                raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

            if bot.status != "active":
                bot.status = "active"
                bot_repository.update(bot)

            bot_run = self._ensure_running_run(self._build_bot_run_service(db), bot_id, trigger_type="manual")
            self._record_event(
                db,
                bot_run.id,
                event_type="system",
                level="info",
                message="bot_resume_requested",
                payload={"bot_status": bot.status},
            )
            db.commit()

            return BotControlRead(bot_id=bot.id, status=bot.status, is_paused=False)

    def get_bot_status(self, bot_id: int) -> BotStatusRead:
        with self.session_factory() as db:
            return self._build_status(db, bot_id)

    def list_bot_dashboard(self) -> BotDashboardRead:
        with self.session_factory() as db:
            bots = BotRepository(db).list_all()
            items = [self._build_dashboard_item(db, bot) for bot in bots]
            return BotDashboardRead(items=items)

    def get_bot_summary(self, bot_id: int, activity_limit: int = 10) -> BotSummaryRead:
        with self.session_factory() as db:
            bot = BotRepository(db).get_by_id(bot_id)
            if bot is None:
                raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")
            return self._build_summary(db, bot, activity_limit=activity_limit)

    def _run_bot_once_sync(self, bot_id: int) -> BotManualRunRead:
        with self.session_factory() as db:
            bot_repository = BotRepository(db)
            bot = bot_repository.get_by_id(bot_id)
            if bot is None:
                raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

            previous_event = RunEventRepository(db).get_latest_for_bot(bot_id)
            profile = ExecutionProfileRepository(db).get_by_bot_id(bot_id)
            if bot.status == "paused":
                latest_event = self._record_manual_skip(
                    db,
                    bot_id,
                    message="bot_skipped_paused",
                    payload={"bot_status": bot.status},
                )
                return self._build_manual_run_result(db, bot_id=bot_id, latest_event=latest_event)
            if bot.status != "active":
                latest_event = self._record_manual_skip(
                    db,
                    bot_id,
                    message="bot_not_active",
                    payload={"bot_status": bot.status},
                )
                return self._build_manual_run_result(db, bot_id=bot_id, latest_event=latest_event)
            if profile is None:
                latest_event = self._record_manual_skip(
                    db,
                    bot_id,
                    message="execution_profile_missing",
                    payload=None,
                )
                return self._build_manual_run_result(db, bot_id=bot_id, latest_event=latest_event)
            if not profile.is_enabled:
                latest_event = self._record_manual_skip(
                    db,
                    bot_id,
                    message="execution_profile_disabled",
                    payload={"execution_profile_enabled": False},
                )
                return self._build_manual_run_result(db, bot_id=bot_id, latest_event=latest_event)

            self._evaluate_bot(db, bot_id, record_noop_events=True)
            latest_event = RunEventRepository(db).get_latest_for_bot(bot_id)
            return self._build_manual_run_result(
                db,
                bot_id=bot_id,
                latest_event=latest_event if latest_event is not None and latest_event != previous_event else None,
            )

    def _run_cycle_sync(self) -> None:
        if not self.config.enabled:
            return

        with self.session_factory() as db:
            bot_repository = BotRepository(db)
            bots = bot_repository.list_all()
            for bot in bots:
                try:
                    self._evaluate_bot(db, bot.id, record_noop_events=False)
                except Exception:
                    db.rollback()
                    logger.exception("bot_runner_bot_error", extra={"bot_id": bot.id})
                    active_run = BotRunRepository(db).get_active_for_bot(bot.id)
                    if active_run is not None:
                        self._record_event(
                            db,
                            active_run.id,
                            event_type="error",
                            level="error",
                            message="error",
                            payload={"detail": "Bot runner evaluation failed"},
                        )
                        db.commit()

    async def _run_loop(self) -> None:
        try:
            while True:
                await self.run_cycle()
                await asyncio.sleep(self.config.poll_interval_seconds)
        except asyncio.CancelledError:
            logger.info("bot_runner_cancelled")
            raise

    def _evaluate_bot(self, db, bot_id: int, *, record_noop_events: bool = False) -> None:
        bot_repository = BotRepository(db)
        strategy_repository = StrategyRepository(db)
        profile_repository = ExecutionProfileRepository(db)
        portfolio_repository = PortfolioRepository(db)
        bot_run_service = self._build_bot_run_service(db)

        bot = bot_repository.get_by_id(bot_id)
        if bot is None:
            return
        if bot.status == "paused":
            if record_noop_events:
                self._record_paused_skip(db, bot.id)
            return
        if bot.status != "active":
            return

        profile = profile_repository.get_by_bot_id(bot_id)
        strategy = strategy_repository.get_by_id(bot.strategy_id)
        if strategy is None:
            raise NotFoundError(f"Strategy with id {bot.strategy_id} was not found", error_code="strategy_not_found")
        if profile is None or not profile.is_enabled:
            return

        bot_run = self._ensure_running_run(bot_run_service, bot_id, trigger_type="system")
        if not strategy.is_active:
            if record_noop_events:
                self._record_event(
                    db,
                    bot_run.id,
                    event_type="system",
                    level="info",
                    message="strategy_inactive",
                    payload={"symbol": strategy.symbol, "strategy_id": strategy.id},
                )
                db.commit()
            return

        strategy_type = self._strategy_type(strategy)
        latest_price = self._get_latest_price(strategy.symbol)
        position = portfolio_repository.get_position_by_symbol(strategy.symbol)
        position_quantity = position.quantity if position is not None else ZERO
        candles = None
        candle_source = None
        if strategy_type in {
            MOVING_AVERAGE_CROSS_STRATEGY_TYPE,
            RSI_THRESHOLD_STRATEGY_TYPE,
            BOLLINGER_BANDS_STRATEGY_TYPE,
            MACD_CROSSOVER_STRATEGY_TYPE,
        }:
            candle_limit = StrategyEngine.required_candle_count(
                strategy_type=strategy_type,
                parameters=strategy.parameters,
            )
            candle_source = self._strategy_candle_source(strategy.parameters)
            if candle_limit is not None:
                candles = self._load_recent_strategy_candles(
                    db,
                    strategy=strategy,
                    limit=candle_limit,
                    source=candle_source,
                )

        decision = StrategyEngine.evaluate(
            strategy_type=strategy_type,
            parameters=strategy.parameters,
            profile=profile,
            latest_price=latest_price,
            position_quantity=position_quantity,
            candles=candles,
        )
        decision_payload = decision.event_payload()

        if strategy_type != PRICE_THRESHOLD_STRATEGY_TYPE:
            decision_payload["strategy_type"] = strategy_type
        if strategy_type in {
            MOVING_AVERAGE_CROSS_STRATEGY_TYPE,
            RSI_THRESHOLD_STRATEGY_TYPE,
            BOLLINGER_BANDS_STRATEGY_TYPE,
            MACD_CROSSOVER_STRATEGY_TYPE,
        }:
            decision_payload["timeframe"] = strategy.timeframe
            if candle_source is not None:
                decision_payload["candle_source"] = candle_source

        if strategy_type not in {
            PRICE_THRESHOLD_STRATEGY_TYPE,
            MOVING_AVERAGE_CROSS_STRATEGY_TYPE,
            RSI_THRESHOLD_STRATEGY_TYPE,
            BOLLINGER_BANDS_STRATEGY_TYPE,
            MACD_CROSSOVER_STRATEGY_TYPE,
        }:
            if record_noop_events:
                self._record_event(
                    db,
                    bot_run.id,
                    event_type="system",
                    level="warning",
                    message="unsupported_strategy_type",
                    payload={"symbol": strategy.symbol, **decision_payload},
                )
                db.commit()
            return

        if decision.metadata.get("parameter") is not None:
            if record_noop_events:
                self._record_event(
                    db,
                    bot_run.id,
                    event_type="system",
                    level="warning",
                    message="evaluation_skipped",
                    payload={"symbol": strategy.symbol, **decision_payload, "reason": "invalid_strategy_parameter"},
                )
                db.commit()
            return

        cooldown_until = self._get_cooldown_until(RunEventRepository(db), bot.id, profile.cooldown_seconds)

        if (
            decision.action == "buy"
            and position_quantity <= ZERO
            and cooldown_until is not None
            and self.now_provider() < cooldown_until
        ):
            if record_noop_events:
                self._record_event(
                    db,
                    bot_run.id,
                    event_type="system",
                    level="info",
                    message="cooldown_active",
                    payload={"symbol": strategy.symbol, "cooldown_until": cooldown_until.isoformat(), **decision_payload},
                )
                db.commit()
            return

        risk_manager = self.risk_manager
        if not self._risk_manager_override:
            risk_manager = RiskManager(RiskLimits.from_profile(profile))
        risk_quantity = position_quantity if decision.action == "sell" else decision.metadata.get("_order_quantity")
        risk_decision = risk_manager.evaluate(
            action=decision.action,
            quantity=risk_quantity,
            current_position_quantity=position_quantity,
            entry_price=position.average_entry_price if position is not None else None,
            current_price=decision.current_price if decision.current_price is not None else latest_price,
        )
        if not risk_decision.allowed:
            if decision.action in {"buy", "sell"} and risk_quantity is not None:
                ExecutionAttemptService(ExecutionAttemptRepository(db)).record(
                    bot_id=bot.id,
                    strategy_id=strategy.id,
                    symbol=strategy.symbol,
                    side=decision.action,
                    mode="paper" if bot.is_paper else "live",
                    broker="paper" if bot.is_paper else None,
                    requested_quantity=risk_quantity,
                    requested_price=decision.current_price if decision.current_price is not None else latest_price,
                    decision_reason=decision_payload.get("detail") or decision_payload.get("reason"),
                    risk_status=risk_decision.reason,
                    safety_status=None,
                    final_status="blocked_by_risk",
                    final_reason=risk_decision.reason,
                    metadata={"decision": decision_payload, "risk": risk_decision.details},
                )
            self._record_event(
                db,
                bot_run.id,
                event_type="system",
                level="warning",
                message="risk_limit_blocked",
                payload={
                    **decision_payload,
                    "symbol": strategy.symbol,
                    "reason": risk_decision.reason,
                    "detail": risk_decision.reason,
                    "decision": "skipped",
                    "risk": risk_decision.details,
                },
            )
            db.commit()
            return

        execution_action = risk_decision.action
        if risk_decision.reason == RISK_REASON_STOP_LOSS_TRIGGERED:
            decision_payload = {
                **decision_payload,
                "decision": "sell",
                "reason": risk_decision.reason,
                "detail": risk_decision.reason,
                "risk": risk_decision.details,
            }

        if execution_action == "skip":
            if record_noop_events:
                self._record_event(
                    db,
                    bot_run.id,
                    event_type="system",
                    level="warning",
                    message="evaluation_skipped",
                    payload={"symbol": strategy.symbol, **decision_payload},
                )
                db.commit()
            return

        if execution_action == "hold":
            if record_noop_events:
                self._record_event(
                    db,
                    bot_run.id,
                    event_type="log",
                    level="info",
                    message="evaluation_no_signal",
                    payload={"symbol": strategy.symbol, **decision_payload},
                )
                db.commit()
            return

        quantity = decision.metadata.get("_order_quantity")
        if execution_action == "sell":
            quantity = position_quantity

        if quantity is None:
            detail = "strategy quantity is missing"
            if strategy_type == PRICE_THRESHOLD_STRATEGY_TYPE:
                detail = "strategy quantity is missing and execution profile order_quantity is not configured"
            if record_noop_events:
                self._record_event(
                    db,
                    bot_run.id,
                    event_type="system",
                    level="warning",
                    message="evaluation_skipped",
                    payload={
                        **decision_payload,
                        "reason": "order_quantity_not_configured",
                        "detail": detail,
                        "decision": "skipped",
                        "symbol": strategy.symbol,
                    },
                )
                db.commit()
            return

        self._record_event(
            db,
            bot_run.id,
            event_type="system",
            level="info",
            message=f"{execution_action}_signal",
            payload={
                "symbol": strategy.symbol,
                "quantity": str(quantity),
                **decision_payload,
            },
        )
        db.commit()

        if not bot.is_paper:
            ExecutionAttemptService(ExecutionAttemptRepository(db)).record(
                bot_id=bot.id,
                strategy_id=strategy.id,
                symbol=strategy.symbol,
                side=execution_action,
                mode="live",
                broker=None,
                requested_quantity=quantity,
                requested_price=decision.current_price if decision.current_price is not None else latest_price,
                decision_reason=decision_payload.get("detail") or decision_payload.get("reason"),
                risk_status=risk_decision.reason,
                safety_status="live_execution_disabled",
                final_status="blocked_by_safety",
                final_reason="live_mode_not_implemented",
                metadata={"decision": decision_payload},
            )
            self._record_event(
                db,
                bot_run.id,
                event_type="system",
                level="warning",
                message="live_mode_not_implemented",
                payload={"side": execution_action, "symbol": strategy.symbol, "quantity": str(quantity), **decision_payload},
            )
            db.commit()
            return

        attempt_repository = ExecutionAttemptRepository(db)
        safety_guard = ExecutionSafetyGuard(
            ExecutionSafetyConfig(
                global_enabled=self.config.execution_global_enabled,
                live_enabled=self.config.execution_live_enabled,
                testnet_order_submission_enabled=self.config.binance_testnet_order_submission_enabled,
                max_order_notional=self.config.execution_max_order_notional,
                max_daily_order_count=self.config.execution_max_daily_order_count,
                max_daily_loss=self.config.execution_max_daily_loss,
            ),
            daily_limit_service=ExecutionDailyLimitService(
                attempt_repository,
                paper_accounting_repository=PaperAccountingRepository(db),
                now_provider=self.now_provider,
            ),
        )
        safety_decision = safety_guard.validate_order(
            PaperOrderIntent(
                bot_id=bot.id,
                strategy_id=strategy.id,
                symbol=strategy.symbol,
                side=execution_action,
                quantity=quantity,
                mode="paper",
                decision_reason=decision_payload.get("detail") or decision_payload.get("reason"),
                decision_metadata=decision_payload,
            ),
            broker="paper",
            market_price=decision.current_price if decision.current_price is not None else latest_price,
        )
        if not safety_decision.allowed:
            ExecutionAttemptService(attempt_repository).record(
                bot_id=bot.id,
                strategy_id=strategy.id,
                symbol=strategy.symbol,
                side=execution_action,
                mode="paper",
                broker="paper",
                requested_quantity=quantity,
                requested_price=decision.current_price if decision.current_price is not None else latest_price,
                decision_reason=decision_payload.get("detail") or decision_payload.get("reason"),
                risk_status=risk_decision.reason,
                safety_status=safety_decision.reason,
                final_status="blocked_by_safety",
                final_reason=safety_decision.reason,
                metadata={**safety_decision.metadata, "decision": decision_payload},
            )
            self._record_event(
                db,
                bot_run.id,
                event_type="system",
                level="warning",
                message="order_rejected",
                payload={
                    "side": execution_action,
                    "symbol": strategy.symbol,
                    "message": safety_decision.reason,
                    **decision_payload,
                },
            )
            db.commit()
            return

        execution_service = SimulatedExecutionService(
            repository=portfolio_repository,
            market_data_service=self.market_data_service,
            simulation_enabled=self.config.simulation_enabled,
            fee_bps=self.config.simulation_fee_bps,
            slippage_bps=self.config.simulation_slippage_bps,
            safety_guard=safety_guard,
            attempt_service=ExecutionAttemptService(attempt_repository),
        )
        result = execution_service.submit_order_intent(
            PaperOrderIntent(
                bot_id=bot.id,
                strategy_id=strategy.id,
                symbol=strategy.symbol,
                side=execution_action,
                quantity=quantity,
                mode="paper",
                decision_reason=decision_payload.get("detail") or decision_payload.get("reason"),
                decision_metadata=decision_payload,
            )
        )

        if result.execution_attempt is None:
            ExecutionAttemptService(attempt_repository).record(
                bot_id=bot.id,
                strategy_id=strategy.id,
                symbol=strategy.symbol,
                side=execution_action,
                mode="paper",
                broker="paper",
                requested_quantity=quantity,
                requested_price=decision.current_price if decision.current_price is not None else latest_price,
                decision_reason=decision_payload.get("detail") or decision_payload.get("reason"),
                risk_status=risk_decision.reason,
                safety_status="allowed" if result.accepted else result.order.rejection_reason if result.order is not None else result.message,
                final_status="filled" if result.accepted else "rejected_by_broker",
                final_reason=result.message,
                order_id=result.order.id if result.order is not None else None,
                metadata={
                    "decision": decision_payload,
                    "fill_id": result.fill.id if result.fill is not None else None,
                },
            )

        self._record_event(
            db,
            bot_run.id,
            event_type="system",
            level="info" if result.accepted else "warning",
            message="order_filled" if result.accepted else "order_rejected",
            payload={
                "side": execution_action,
                "symbol": strategy.symbol,
                "message": result.message,
                "order_id": result.order.id if result.order is not None else None,
                "fill_id": result.fill.id if result.fill is not None else None,
                **decision_payload,
            },
        )
        db.commit()

    def _ensure_running_run(self, bot_run_service: BotRunService, bot_id: int, trigger_type: str) -> BotRun:
        existing = bot_run_service.repository.get_active_for_bot(bot_id)
        if existing is not None:
            if existing.status != "running":
                return bot_run_service.update(bot_id, existing.id, BotRunUpdate(status="running"))
            return existing

        bot_run = bot_run_service.create(bot_id, BotRunCreate(trigger_type=trigger_type))
        return bot_run_service.update(bot_id, bot_run.id, BotRunUpdate(status="running", summary="Bot runner active"))

    def _build_status(self, db, bot_id: int) -> BotStatusRead:
        bot_repository = BotRepository(db)
        strategy_repository = StrategyRepository(db)
        profile_repository = ExecutionProfileRepository(db)
        bot_run_repository = BotRunRepository(db)
        run_event_repository = RunEventRepository(db)
        portfolio_repository = PortfolioRepository(db)

        bot = bot_repository.get_by_id(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

        strategy = strategy_repository.get_by_id(bot.strategy_id)
        if strategy is None:
            raise NotFoundError(f"Strategy with id {bot.strategy_id} was not found", error_code="strategy_not_found")

        profile = profile_repository.get_by_bot_id(bot_id)
        if profile is None:
            raise NotFoundError(
                f"Execution profile for bot with id {bot_id} was not found",
                error_code="execution_profile_not_found",
            )

        active_run = bot_run_repository.get_active_for_bot(bot_id)
        latest_event = run_event_repository.get_latest_for_bot(bot_id)
        position = portfolio_repository.get_position_by_symbol(strategy.symbol)
        latest_price = self._get_latest_price(strategy.symbol)
        cooldown_until = self._get_cooldown_until(run_event_repository, bot.id, profile.cooldown_seconds)
        cooldown_active = cooldown_until is not None and self.now_provider() < cooldown_until

        return BotStatusRead(
            bot_id=bot.id,
            bot_name=bot.name,
            bot_status=bot.status,
            is_paused=bot.status == "paused",
            execution_profile_enabled=profile.is_enabled,
            runner_enabled=self.config.enabled and bot.status == "active" and profile.is_enabled,
            strategy_type=self._strategy_type(strategy),
            symbol=strategy.symbol,
            active_run_id=active_run.id if active_run is not None else None,
            active_run_status=active_run.status if active_run is not None else None,
            latest_price=latest_price,
            current_position_quantity=position.quantity if position is not None else ZERO,
            cooldown_seconds=profile.cooldown_seconds,
            cooldown_active=cooldown_active,
            cooldown_until=cooldown_until if cooldown_active else None,
            last_event_message=latest_event.message if latest_event is not None else None,
            last_event_at=latest_event.created_at if latest_event is not None else None,
            poll_interval_seconds=self.config.poll_interval_seconds,
        )

    def _build_dashboard_item(self, db, bot) -> BotDashboardItemRead:
        strategy = StrategyRepository(db).get_by_id(bot.strategy_id)
        if strategy is None:
            raise NotFoundError(f"Strategy with id {bot.strategy_id} was not found", error_code="strategy_not_found")

        profile = ExecutionProfileRepository(db).get_by_bot_id(bot.id)
        position = PortfolioRepository(db).get_position_by_symbol(strategy.symbol)
        run_event_repository = RunEventRepository(db)
        latest_price = self._get_latest_price(strategy.symbol)
        cooldown_until = None
        if profile is not None:
            cooldown_until = self._get_cooldown_until(run_event_repository, bot.id, profile.cooldown_seconds)
        cooldown_active = cooldown_until is not None and self.now_provider() < cooldown_until

        return BotDashboardItemRead(
            bot_id=bot.id,
            name=bot.name,
            status=bot.status,
            is_paused=bot.status == "paused",
            strategy_type=self._strategy_type(strategy),
            symbol=strategy.symbol,
            cooldown_active=cooldown_active,
            cooldown_until=cooldown_until if cooldown_active else None,
            current_position_qty=position.quantity if position is not None else ZERO,
            last_price=latest_price,
            updated_at=bot.updated_at,
        )

    def _build_summary(self, db, bot, activity_limit: int) -> BotSummaryRead:
        dashboard_item = self._build_dashboard_item(db, bot)
        strategy = StrategyRepository(db).get_by_id(bot.strategy_id)
        if strategy is None:
            raise NotFoundError(f"Strategy with id {bot.strategy_id} was not found", error_code="strategy_not_found")
        profile = ExecutionProfileRepository(db).get_by_bot_id(bot.id)
        portfolio_repository = PortfolioRepository(db)
        recent_events = RunEventRepository(db).list_recent_for_bot(bot.id, limit=activity_limit)

        return BotSummaryRead(
            bot_id=dashboard_item.bot_id,
            name=dashboard_item.name,
            status=dashboard_item.status,
            is_paused=dashboard_item.is_paused,
            strategy_type=dashboard_item.strategy_type,
            strategy_name=strategy.name,
            strategy_timeframe=strategy.timeframe,
            strategy_parameters=strategy.parameters or {},
            symbol=dashboard_item.symbol,
            cooldown_seconds=profile.cooldown_seconds if profile is not None else None,
            cooldown_active=dashboard_item.cooldown_active,
            cooldown_until=dashboard_item.cooldown_until,
            current_position_qty=dashboard_item.current_position_qty,
            last_price=dashboard_item.last_price,
            updated_at=dashboard_item.updated_at,
            buy_below_price=profile.entry_below if profile is not None else None,
            sell_above_price=profile.exit_above if profile is not None else None,
            recent_activity=[build_activity_item(event, portfolio_repository) for event in recent_events],
        )

    def _build_manual_run_result(self, db, bot_id: int, latest_event) -> BotManualRunRead:
        bot = BotRepository(db).get_by_id(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

        dashboard_item = self._build_dashboard_item(db, bot)
        portfolio_repository = PortfolioRepository(db)
        recent_events = RunEventRepository(db).list_recent_for_bot(bot_id, limit=3)
        action, message = self._classify_manual_run_event(latest_event)

        return BotManualRunRead(
            bot_id=bot_id,
            status=dashboard_item.status,
            is_paused=dashboard_item.is_paused,
            action=action,
            message=message,
            cooldown_active=dashboard_item.cooldown_active,
            cooldown_until=dashboard_item.cooldown_until,
            current_position_qty=dashboard_item.current_position_qty,
            last_price=dashboard_item.last_price,
            decision_explanation=self._build_decision_explanation(latest_event, action, message),
            recent_activity_preview=[build_activity_item(event, portfolio_repository) for event in recent_events],
        )

    @staticmethod
    def _build_decision_explanation(run_event, action: str, message: str) -> BotDecisionExplanationRead | None:
        if run_event is None:
            return None

        payload = run_event.payload or {}
        reason = payload.get("detail") or payload.get("reason") or message
        decision = payload.get("decision") or action

        return BotDecisionExplanationRead(
            current_price=payload.get("current_price"),
            buy_below=payload.get("buy_below"),
            sell_above=payload.get("sell_above"),
            position_qty=payload.get("position_qty"),
            short_window=payload.get("short_window"),
            long_window=payload.get("long_window"),
            previous_short_ma=payload.get("previous_short_ma"),
            previous_long_ma=payload.get("previous_long_ma"),
            current_short_ma=payload.get("current_short_ma"),
            current_long_ma=payload.get("current_long_ma"),
            candles_used=payload.get("candles_used"),
            decision=decision,
            reason=reason,
        )

    @staticmethod
    def _classify_manual_run_event(run_event) -> tuple[str, str]:
        if run_event is None:
            return "no_action", "no_action"

        if run_event.message == "order_filled":
            side = (run_event.payload or {}).get("side")
            if side == "buy":
                return "bought", "buy_filled"
            if side == "sell":
                return "sold", "sell_filled"
            return "no_action", run_event.message

        if run_event.message in {
            "cooldown_active",
            "evaluation_skipped",
            "unsupported_strategy_type",
            "bot_skipped_paused",
            "bot_not_active",
            "execution_profile_missing",
            "execution_profile_disabled",
            "strategy_inactive",
            "live_mode_not_implemented",
            "order_rejected",
        }:
            return "skipped", run_event.message

        if run_event.message == "evaluation_no_signal":
            return "no_action", run_event.message

        if run_event.message.endswith("_signal"):
            return "no_action", run_event.message

        return "no_action", run_event.message

    def _cancel_active_runs(self, reason: str) -> None:
        with self.session_factory() as db:
            bot_repository = BotRepository(db)
            bot_run_service = self._build_bot_run_service(db)
            for bot in bot_repository.list_all(status="active"):
                active_run = bot_run_service.repository.get_active_for_bot(bot.id)
                if active_run is None:
                    continue
                bot_run_service.update(bot.id, active_run.id, BotRunUpdate(status="cancelled", summary=reason))
                self._record_event(
                    db,
                    active_run.id,
                    event_type="lifecycle",
                    level="info",
                    message="stopped",
                    payload={"reason": "shutdown"},
                )
            db.commit()

    def _record_event(self, db, bot_run_id: int, event_type: str, level: str, message: str, payload: dict | None) -> None:
        db.add(
            RunEvent(
                bot_run_id=bot_run_id,
                event_type=event_type,
                level=level,
                message=message,
                payload=payload,
            )
        )

    def _record_manual_skip(self, db, bot_id: int, message: str, payload: dict | None) -> RunEvent:
        bot_run = BotRunRepository(db).get_active_for_bot(bot_id)
        if bot_run is None:
            now = self.now_provider()
            bot_run = BotRun(
                bot_id=bot_id,
                trigger_type="manual",
                status="succeeded",
                summary=message,
                started_at=now,
                finished_at=now,
            )
            db.add(bot_run)
            db.flush()

        run_event = RunEvent(
            bot_run_id=bot_run.id,
            event_type="system",
            level="info",
            message=message,
            payload=payload,
        )
        db.add(run_event)
        db.commit()
        db.refresh(run_event)
        return run_event

    def _record_paused_skip(self, db, bot_id: int) -> None:
        active_run = BotRunRepository(db).get_active_for_bot(bot_id)
        if active_run is None:
            return
        self._record_event(
            db,
            active_run.id,
            event_type="system",
            level="info",
            message="bot_skipped_paused",
            payload={"bot_status": "paused"},
        )
        db.commit()

    def _build_bot_run_service(self, db) -> BotRunService:
        return BotRunService(
            BotRunRepository(db),
            BotRepository(db),
            ExecutionProfileRepository(db),
            RunEventRepository(db),
        )

    def _load_recent_strategy_candles(self, db, *, strategy, limit: int, source: str | None = None):
        return MarketCandleRepository(db).list_recent(
            symbol=strategy.symbol,
            timeframe=strategy.timeframe,
            limit=limit,
            source=source,
        )

    def _get_latest_price(self, symbol: str) -> Decimal | None:
        latest = self.market_data_service.get_latest(symbol)
        if latest is None or not isinstance(latest, MarketEvent):
            return None
        return latest.price or latest.close

    def _get_cooldown_until(self, run_event_repository: RunEventRepository, bot_id: int, cooldown_seconds: int) -> datetime | None:
        latest_sell_event = run_event_repository.get_latest_order_filled_for_bot(bot_id, side="sell")
        if latest_sell_event is None:
            return None
        return self._normalize_timestamp(latest_sell_event.created_at) + timedelta(seconds=cooldown_seconds)

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _strategy_candle_source(parameters: dict | None) -> str | None:
        if not parameters:
            return None
        source = parameters.get("candle_source") or parameters.get("source")
        if source is None:
            return None
        normalized = str(source).strip()
        return normalized or None

    @staticmethod
    def _strategy_type(strategy) -> str:
        return StrategyEngine.strategy_type(strategy)
