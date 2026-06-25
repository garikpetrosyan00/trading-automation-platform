from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import AppError
from app.data.schemas import MarketEvent
from app.models.execution_attempt import ExecutionAttempt
from app.models.position import Position
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.schemas.execution import ExecutionPositionSnapshot, MarketOrderRequest
from app.services.brokers.base import BrokerOrderIntent, BrokerOrderResult
from app.services.brokers.safety import ExecutionSafetyDecision, ExecutionSafetyGuard
from app.services.draft_balance import DraftBalanceService
from app.services.execution_attempt import ExecutionAttemptService
from app.services.execution_limits import ExecutionDailyLimitService
from app.services.paper_equity_snapshot import PaperEquitySnapshotService
from app.services.paper_position import PaperPositionService
from app.services.paper_portfolio import PaperPortfolioResult, PaperPortfolioService

ZERO = Decimal("0")
BPS_DIVISOR = Decimal("10000")
QUOTE_ASSET_SUFFIXES = ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH")


@dataclass
class ExecutionResult:
    accepted: bool
    status: str
    message: str
    order: SimulatedOrder | None
    fill: SimulatedFill | None
    updated_cash_balance: Decimal
    position: Position | None
    execution_attempt: ExecutionAttempt | None = None


@dataclass(frozen=True)
class PaperOrderIntent(BrokerOrderIntent):
    pass


class PaperExecutionService:
    def __init__(
        self,
        repository: PortfolioRepository,
        market_data_service,
        simulation_enabled: bool,
        fee_bps: Decimal,
        slippage_bps: Decimal,
        safety_guard: ExecutionSafetyGuard | None = None,
        attempt_service: ExecutionAttemptService | None = None,
        safety_rejections_create_order: bool = True,
    ):
        self.repository = repository
        self.market_data_service = market_data_service
        self.simulation_enabled = simulation_enabled
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.safety_guard = safety_guard or ExecutionSafetyGuard()
        if self.safety_guard.daily_limit_service is None:
            self.safety_guard.daily_limit_service = ExecutionDailyLimitService(
                ExecutionAttemptRepository(repository.db)
            )
        self.attempt_service = attempt_service
        self.safety_rejections_create_order = safety_rejections_create_order

    def submit_market_order(self, payload: MarketOrderRequest) -> ExecutionResult:
        intent = PaperOrderIntent(
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
        )
        return self.submit_order_intent(intent)

    def submit_broker_order(self, intent: BrokerOrderIntent) -> BrokerOrderResult:
        result = self.submit_order_intent(PaperOrderIntent(**intent.__dict__))
        return self._build_broker_result(result)

    def submit_order_intent(self, intent: PaperOrderIntent) -> ExecutionResult:
        account = self.repository.get_account()
        if account is None:
            raise ValueError("Portfolio account is not initialized")

        symbol = intent.symbol.strip().upper()
        position = self.repository.get_position_by_symbol(symbol)
        latest_price = self._get_latest_price(symbol)

        if intent.mode != "paper":
            return self._reject_order(
                intent=intent,
                symbol=symbol,
                requested_price_snapshot=latest_price,
                reason="Live execution is not implemented",
                cash_balance=account.cash_balance,
                position=position,
            )

        if not self.simulation_enabled:
            return self._reject_order(
                intent=intent,
                symbol=symbol,
                requested_price_snapshot=latest_price,
                reason="Simulation is disabled",
                cash_balance=account.cash_balance,
                position=position,
            )

        invalid_reason = self._validate_intent(intent)
        if invalid_reason is not None:
            return self._reject_order(
                intent=intent,
                symbol=symbol,
                requested_price_snapshot=latest_price,
                reason=invalid_reason,
                cash_balance=account.cash_balance,
                position=position,
            )

        if latest_price is None:
            return self._reject_order(
                intent=intent,
                symbol=symbol,
                requested_price_snapshot=None,
                reason=f"No latest market price available for symbol {symbol}",
                cash_balance=account.cash_balance,
                position=position,
            )

        if latest_price <= ZERO:
            return self._reject_order(
                intent=intent,
                symbol=symbol,
                requested_price_snapshot=latest_price,
                reason=f"Invalid latest market price for symbol {symbol}",
                cash_balance=account.cash_balance,
                position=position,
            )

        fill_price = self._apply_slippage(latest_price, intent.side)
        notional = intent.quantity * fill_price
        fee = self._calculate_fee(notional)

        try:
            account = self.repository.get_account_for_update()
            if account is None:
                raise ValueError("Portfolio account is not initialized")
            position = self.repository.get_position_by_symbol(symbol)

            daily_count_decision = self._validate_daily_order_count(intent)
            if not daily_count_decision.allowed:
                attempt = self._record_blocked_attempt(
                    intent=intent,
                    symbol=symbol,
                    requested_price=latest_price,
                    reason=daily_count_decision.reason,
                    metadata=daily_count_decision.metadata,
                )
                if self.safety_rejections_create_order:
                    return self._reject_order(
                        intent=intent,
                        symbol=symbol,
                        requested_price_snapshot=latest_price,
                        reason=daily_count_decision.reason,
                        cash_balance=account.cash_balance,
                        position=position,
                        attempt=attempt,
                        final_status="blocked_by_safety",
                    )
                return self._reject_without_order(
                    intent=intent,
                    symbol=symbol,
                    reason=daily_count_decision.reason,
                    cash_balance=account.cash_balance,
                    position=position,
                    attempt=attempt,
                )

            attempt = self._reserve_attempt(intent=intent, symbol=symbol, requested_price=latest_price)

            safety_decision = self.safety_guard.validate_order(
                intent,
                broker="paper",
                market_price=latest_price,
                skip_daily_order_count=True,
            )
            if not safety_decision.allowed:
                if self.safety_rejections_create_order:
                    return self._reject_order(
                        intent=intent,
                        symbol=symbol,
                        requested_price_snapshot=latest_price,
                        reason=safety_decision.reason,
                        cash_balance=account.cash_balance,
                        position=position,
                        attempt=attempt,
                        final_status="blocked_by_safety",
                    )
                return self._reject_without_order(
                    intent=intent,
                    symbol=symbol,
                    reason=safety_decision.reason,
                    cash_balance=account.cash_balance,
                    position=position,
                    attempt=attempt,
                )

            draft_reserved = False
            if self._uses_draft_balance(intent):
                try:
                    base_asset, quote_asset = self._symbol_assets(symbol)
                    if intent.side == "buy":
                        self._draft_balance_service().reserve_bot_draft_balance_asset(
                            bot_id=intent.bot_id,
                            asset=quote_asset,
                            amount=notional + fee,
                        )
                    else:
                        self._draft_balance_service().reserve_bot_draft_balance_asset(
                            bot_id=intent.bot_id,
                            asset=base_asset,
                            amount=intent.quantity,
                        )
                    draft_reserved = True
                except AppError as exc:
                    return self._reject_without_order(
                        intent=intent,
                        symbol=symbol,
                        reason=exc.error_code,
                        cash_balance=account.cash_balance,
                        position=position,
                        attempt=attempt,
                        final_status="rejected_by_broker",
                    )

            if intent.side == "buy":
                required_cash = notional + fee
                if required_cash > account.cash_balance:
                    if draft_reserved:
                        self._draft_balance_service().release_bot_draft_balance_asset(
                            bot_id=intent.bot_id,
                            asset=quote_asset,
                            amount=required_cash,
                        )
                    return self._reject_order(
                        intent=intent,
                        symbol=symbol,
                        requested_price_snapshot=latest_price,
                        reason="insufficient_paper_cash",
                        cash_balance=account.cash_balance,
                    position=position,
                    attempt=attempt,
                )

                quota_decision = self._reserve_daily_quota(intent)
                if not quota_decision.allowed:
                    if draft_reserved:
                        self._draft_balance_service().release_bot_draft_balance_asset(
                            bot_id=intent.bot_id,
                            asset=quote_asset,
                            amount=required_cash,
                        )
                    self._finalize_attempt(
                        attempt,
                        final_status="blocked_by_safety",
                        final_reason=quota_decision.reason,
                        safety_status=quota_decision.reason,
                        metadata=quota_decision.metadata,
                    )
                    if self.safety_rejections_create_order:
                        return self._reject_order(
                            intent=intent,
                            symbol=symbol,
                            requested_price_snapshot=latest_price,
                            reason=quota_decision.reason,
                            cash_balance=account.cash_balance,
                            position=position,
                            attempt=attempt,
                            final_status="blocked_by_safety",
                        )
                    return self._reject_without_order(
                        intent=intent,
                        symbol=symbol,
                        reason=quota_decision.reason,
                        cash_balance=account.cash_balance,
                        position=position,
                        attempt=attempt,
                    )

                order = self._create_order(intent, symbol, latest_price, status="filled")
                fill = self._create_fill(order, intent, symbol, fill_price, fee)
                accounting_result = PaperPortfolioService(self.repository).apply_fill(fill)
                if not accounting_result.accepted:
                    self.repository.rollback()
                    return self._reject_order(
                        intent=intent,
                        symbol=symbol,
                        requested_price_snapshot=latest_price,
                        reason=accounting_result.message,
                        cash_balance=account.cash_balance,
                        position=position,
                        attempt=None,
                    )

                if draft_reserved:
                    try:
                        self._paper_position_service().apply_buy_fill(
                            bot_id=intent.bot_id,
                            symbol=symbol,
                            base_asset=base_asset,
                            quote_asset=quote_asset,
                            quantity=fill.fill_quantity,
                            fill_price=fill.fill_price,
                            fee=fill.fee,
                        )
                    except AppError as exc:
                        return self._reject_after_settlement_failure(
                            intent=intent,
                            symbol=symbol,
                            requested_price_snapshot=latest_price,
                            reason=exc.error_code,
                            cash_balance=account.cash_balance,
                            position=position,
                        )
                    try:
                        self._draft_balance_service().apply_draft_balance_buy_fill(
                            bot_id=intent.bot_id,
                            base_asset=base_asset,
                            quote_asset=quote_asset,
                            received_base_amount=fill.fill_quantity,
                            spent_quote_amount=(fill.fill_quantity * fill.fill_price) + fill.fee,
                        )
                        self._paper_equity_snapshot_service().create_snapshot(
                            bot_id=intent.bot_id,
                            symbol=symbol,
                            base_asset=base_asset,
                            quote_asset=quote_asset,
                            event_type="buy_fill",
                            source_order_id=order.id,
                            source_fill_id=fill.id,
                        )
                    except AppError as exc:
                        return self._reject_after_settlement_failure(
                            intent=intent,
                            symbol=symbol,
                            requested_price_snapshot=latest_price,
                            reason=exc.error_code,
                            cash_balance=account.cash_balance,
                            position=position,
                        )
                    except Exception:
                        self.repository.rollback()
                        raise

                self._finalize_attempt(
                    attempt,
                    final_status="filled",
                    final_reason="Market buy order filled",
                    order_id=order.id,
                    safety_status="allowed",
                    metadata={
                        "broker": "paper",
                        "symbol": symbol,
                        "side": intent.side,
                        "mode": intent.mode,
                        "fill_id": fill.id,
                        "risk_reducing_exit": intent.side == "sell",
                    },
                )
                self.repository.commit()
                self.repository.refresh(order)
                self.repository.refresh(fill)
                self.repository.refresh(accounting_result.account)
                if accounting_result.position is not None:
                    self.repository.refresh(accounting_result.position)
                return ExecutionResult(
                    accepted=True,
                    status="filled",
                    message="Market buy order filled",
                    order=order,
                    fill=fill,
                    updated_cash_balance=accounting_result.account.cash_balance,
                    position=accounting_result.position,
                    execution_attempt=attempt,
                )

            quota_decision = self._reserve_daily_quota(intent)
            if not quota_decision.allowed:
                if draft_reserved:
                    self._draft_balance_service().release_bot_draft_balance_asset(
                        bot_id=intent.bot_id,
                        asset=base_asset,
                        amount=intent.quantity,
                    )
                self._finalize_attempt(
                    attempt,
                    final_status="blocked_by_safety",
                    final_reason=quota_decision.reason,
                    safety_status=quota_decision.reason,
                    metadata=quota_decision.metadata,
                )
                if self.safety_rejections_create_order:
                    return self._reject_order(
                        intent=intent,
                        symbol=symbol,
                        requested_price_snapshot=latest_price,
                        reason=quota_decision.reason,
                        cash_balance=account.cash_balance,
                        position=position,
                        attempt=attempt,
                        final_status="blocked_by_safety",
                    )
                return self._reject_without_order(
                    intent=intent,
                    symbol=symbol,
                    reason=quota_decision.reason,
                    cash_balance=account.cash_balance,
                    position=position,
                    attempt=attempt,
                )

            order = self._create_order(intent, symbol, latest_price, status="filled")
            fill = self._create_fill(order, intent, symbol, fill_price, fee)
            if draft_reserved:
                try:
                    self._paper_position_service().apply_sell_fill(
                        bot_id=intent.bot_id,
                        symbol=symbol,
                        base_asset=base_asset,
                        quote_asset=quote_asset,
                        quantity=fill.fill_quantity,
                        fill_price=fill.fill_price,
                        fee=fill.fee,
                    )
                except AppError as exc:
                    return self._reject_after_settlement_failure(
                        intent=intent,
                        symbol=symbol,
                        requested_price_snapshot=latest_price,
                        reason=exc.error_code,
                        cash_balance=account.cash_balance,
                        position=position,
                    )
                try:
                    self._draft_balance_service().apply_draft_balance_sell_fill(
                        bot_id=intent.bot_id,
                        base_asset=base_asset,
                        quote_asset=quote_asset,
                        sold_base_amount=fill.fill_quantity,
                        received_quote_amount=(fill.fill_quantity * fill.fill_price) - fill.fee,
                    )
                    self._paper_equity_snapshot_service().create_snapshot(
                        bot_id=intent.bot_id,
                        symbol=symbol,
                        base_asset=base_asset,
                        quote_asset=quote_asset,
                        event_type="sell_fill",
                        source_order_id=order.id,
                        source_fill_id=fill.id,
                    )
                except AppError as exc:
                    return self._reject_after_settlement_failure(
                        intent=intent,
                        symbol=symbol,
                        requested_price_snapshot=latest_price,
                        reason=exc.error_code,
                        cash_balance=account.cash_balance,
                        position=position,
                    )
                except Exception:
                    self.repository.rollback()
                    raise

                accounting_result = self._mirror_legacy_sell_fill_if_possible(
                    fill=fill,
                    account=account,
                    position=position,
                )
            else:
                accounting_result = PaperPortfolioService(self.repository).apply_fill(fill)
                if not accounting_result.accepted:
                    self.repository.rollback()
                    return self._reject_order(
                        intent=intent,
                        symbol=symbol,
                        requested_price_snapshot=latest_price,
                        reason=accounting_result.message,
                        cash_balance=account.cash_balance,
                        position=position,
                        attempt=None,
                    )

            self._finalize_attempt(
                attempt,
                final_status="filled",
                final_reason="Market sell order filled",
                order_id=order.id,
                safety_status="allowed",
                metadata={
                    "broker": "paper",
                    "symbol": symbol,
                    "side": intent.side,
                    "mode": intent.mode,
                    "fill_id": fill.id,
                    "risk_reducing_exit": True,
                },
            )
            self.repository.commit()
            self.repository.refresh(order)
            self.repository.refresh(fill)
            self.repository.refresh(accounting_result.account)
            if accounting_result.position is not None:
                self.repository.refresh(accounting_result.position)
            return ExecutionResult(
                accepted=True,
                status="filled",
                message="Market sell order filled",
                order=order,
                fill=fill,
                updated_cash_balance=accounting_result.account.cash_balance,
                position=accounting_result.position,
                execution_attempt=attempt,
            )
        except Exception:
            self.repository.rollback()
            raise

    def _mirror_legacy_sell_fill_if_possible(
        self,
        *,
        fill: SimulatedFill,
        account,
        position: Position | None,
    ) -> PaperPortfolioResult:
        quantity = fill.fill_quantity if fill.fill_quantity is not None else fill.quantity
        if position is None or position.quantity < quantity:
            return PaperPortfolioResult(
                accepted=True,
                message="Legacy sell mirror skipped",
                account=account,
                position=position,
            )
        result = PaperPortfolioService(self.repository).apply_fill(fill)
        if result.accepted:
            return result
        return PaperPortfolioResult(
            accepted=True,
            message="Legacy sell mirror skipped",
            account=account,
            position=position,
        )

    @staticmethod
    def build_position_snapshot(position: Position | None) -> ExecutionPositionSnapshot | None:
        if position is None:
            return None
        return ExecutionPositionSnapshot(
            symbol=position.symbol,
            quantity=position.quantity,
            average_entry_price=position.average_entry_price,
            realized_pnl=position.realized_pnl,
        )

    def _reject_order(
        self,
        intent: PaperOrderIntent,
        symbol: str,
        requested_price_snapshot: Decimal | None,
        reason: str,
        cash_balance: Decimal,
        position: Position | None,
        attempt: ExecutionAttempt | None = None,
        final_status: str = "rejected_by_broker",
        record_attempt_if_missing: bool = False,
    ) -> ExecutionResult:
        try:
            order = SimulatedOrder(
                symbol=symbol,
                side=intent.side,
                order_type=intent.order_type,
                quantity=intent.quantity,
                requested_price_snapshot=requested_price_snapshot,
                status="rejected",
                mode=intent.mode,
                bot_id=intent.bot_id,
                strategy_id=intent.strategy_id,
                decision_reason=intent.decision_reason,
                decision_metadata=intent.decision_metadata,
                rejection_reason=reason,
            )
            self.repository.save(order)
            self.repository.flush()
            if attempt is None and record_attempt_if_missing and self.attempt_service is not None:
                attempt = self.attempt_service.record(
                    bot_id=intent.bot_id,
                    strategy_id=intent.strategy_id,
                    symbol=symbol,
                    side=intent.side,
                    mode=intent.mode,
                    broker="paper",
                    requested_quantity=intent.quantity,
                    requested_price=requested_price_snapshot,
                    decision_reason=intent.decision_reason,
                    risk_status="allowed",
                    safety_status="allowed" if final_status == "rejected_by_broker" else reason,
                    final_status=final_status,
                    final_reason=reason,
                    order_id=order.id,
                    metadata={
                        "broker": "paper",
                        "symbol": symbol,
                        "side": intent.side,
                        "mode": intent.mode,
                        "fill_id": None,
                    },
                )
            self._finalize_attempt(
                attempt,
                final_status=final_status,
                final_reason=reason,
                order_id=order.id,
                safety_status=reason if final_status == "blocked_by_safety" else "allowed",
                metadata={
                    "broker": "paper",
                    "symbol": symbol,
                    "side": intent.side,
                    "mode": intent.mode,
                    "fill_id": None,
                },
            )
            self.repository.commit()
            self.repository.refresh(order)
            return ExecutionResult(
                accepted=False,
                status="rejected",
                message=reason,
                order=order,
                fill=None,
                updated_cash_balance=cash_balance,
                position=position,
                execution_attempt=attempt,
            )
        except Exception:
            self.repository.rollback()
            raise

    def _reject_after_settlement_failure(
        self,
        *,
        intent: PaperOrderIntent,
        symbol: str,
        requested_price_snapshot: Decimal | None,
        reason: str,
        cash_balance: Decimal,
        position: Position | None,
    ) -> ExecutionResult:
        self.repository.rollback()
        return self._reject_order(
            intent=intent,
            symbol=symbol,
            requested_price_snapshot=requested_price_snapshot,
            reason=reason,
            cash_balance=cash_balance,
            position=position,
            attempt=None,
            final_status="rejected_by_broker",
            record_attempt_if_missing=True,
        )

    def _reject_without_order(
        self,
        intent: PaperOrderIntent,
        symbol: str,
        reason: str,
        cash_balance: Decimal,
        position: Position | None,
        attempt: ExecutionAttempt | None,
        final_status: str = "blocked_by_safety",
    ) -> ExecutionResult:
        try:
            self._finalize_attempt(
                attempt,
                final_status=final_status,
                final_reason=reason,
                safety_status=reason,
                metadata={
                    "broker": "paper",
                    "symbol": symbol,
                    "side": intent.side,
                    "mode": intent.mode,
                    "fill_id": None,
                },
            )
            self.repository.commit()
            return ExecutionResult(
                accepted=False,
                status="rejected",
                message=reason,
                order=None,
                fill=None,
                updated_cash_balance=cash_balance,
                position=position,
                execution_attempt=attempt,
            )
        except Exception:
            self.repository.rollback()
            raise

    def _create_order(
        self,
        intent: PaperOrderIntent,
        symbol: str,
        latest_price: Decimal,
        status: str,
    ) -> SimulatedOrder:
        order = SimulatedOrder(
            bot_id=intent.bot_id,
            strategy_id=intent.strategy_id,
            symbol=symbol,
            side=intent.side,
            order_type=intent.order_type,
            quantity=intent.quantity,
            requested_price_snapshot=latest_price,
            status=status,
            mode=intent.mode,
            decision_reason=intent.decision_reason,
            decision_metadata=intent.decision_metadata,
        )
        self.repository.save(order)
        self.repository.flush()
        return order

    def _create_fill(
        self,
        order: SimulatedOrder,
        intent: PaperOrderIntent,
        symbol: str,
        fill_price: Decimal,
        fee: Decimal,
    ) -> SimulatedFill:
        fill = SimulatedFill(
            order_id=order.id,
            symbol=symbol,
            side=intent.side,
            quantity=intent.quantity,
            fill_quantity=intent.quantity,
            fill_price=fill_price,
            fee=fee,
            source="paper",
        )
        self.repository.save(fill)
        self.repository.flush()
        return fill

    def _validate_daily_order_count(self, intent: PaperOrderIntent):
        config = self.safety_guard.config
        daily_limit_service = self.safety_guard.daily_limit_service
        metadata = {
            "broker": "paper",
            "mode": intent.mode,
            "symbol": intent.symbol.strip().upper() if intent.symbol else intent.symbol,
            "side": intent.side,
            "risk_reducing_exits_allowed": True,
        }
        if intent.side == "sell":
            return ExecutionSafetyDecision(
                allowed=True,
                reason="risk_reducing_exit_allowed",
                metadata={
                    **metadata,
                    "daily_order_count_limit_applies_to": "buy",
                },
            )
        if config.max_daily_order_count is None or config.max_daily_order_count <= 0:
            return self.safety_guard.validate_order(
                intent,
                broker="paper",
                market_price=None,
                skip_daily_order_count=True,
            )
        if daily_limit_service is None:
            return self.safety_guard._blocked("daily_limit_service_unavailable", metadata)
        snapshot = daily_limit_service.count_successful_orders_today(bot_id=intent.bot_id)
        if snapshot.count >= config.max_daily_order_count:
            return self.safety_guard._blocked(
                "max_daily_order_count_exceeded",
                {
                    **metadata,
                    "bot_id": intent.bot_id,
                    "daily_order_count": snapshot.count,
                    "max_daily_order_count": config.max_daily_order_count,
                    "day_start": snapshot.day_start.isoformat(),
                },
            )
        return ExecutionSafetyDecision(allowed=True, reason="allowed", metadata=metadata)

    def _reserve_daily_quota(self, intent: PaperOrderIntent) -> ExecutionSafetyDecision:
        config = self.safety_guard.config
        daily_limit_service = self.safety_guard.daily_limit_service
        metadata = {
            "broker": "paper",
            "mode": intent.mode,
            "symbol": intent.symbol.strip().upper() if intent.symbol else intent.symbol,
            "side": intent.side,
            "risk_reducing_exits_allowed": True,
            "bot_id": intent.bot_id,
        }
        if daily_limit_service is None:
            return self.safety_guard._blocked("daily_limit_service_unavailable", metadata)

        reservation = daily_limit_service.reserve_accepted_order_quota(
            bot_id=intent.bot_id,
            max_daily_order_count=config.max_daily_order_count,
            enforce_limit=intent.side == "buy",
        )
        if not reservation.allowed:
            return self.safety_guard._blocked(
                "max_daily_order_count_exceeded",
                {
                    **metadata,
                    "daily_order_count": reservation.count,
                    "max_daily_order_count": config.max_daily_order_count,
                    "day_start": reservation.day_start.isoformat(),
                },
            )
        return ExecutionSafetyDecision(
            allowed=True,
            reason="allowed",
            metadata={
                **metadata,
                "daily_order_count": reservation.count,
                "max_daily_order_count": config.max_daily_order_count,
                "day_start": reservation.day_start.isoformat(),
            },
        )

    def _reserve_attempt(
        self,
        *,
        intent: PaperOrderIntent,
        symbol: str,
        requested_price: Decimal | None,
    ) -> ExecutionAttempt | None:
        if self.attempt_service is None:
            return None
        return self.attempt_service.record(
            bot_id=intent.bot_id,
            strategy_id=intent.strategy_id,
            symbol=symbol,
            side=intent.side,
            mode=intent.mode,
            broker="paper",
            requested_quantity=intent.quantity,
            requested_price=requested_price,
            decision_reason=intent.decision_reason,
            risk_status="allowed",
            safety_status="reserved",
            final_status="created",
            final_reason="paper_order_slot_reserved",
            metadata={
                "broker": "paper",
                "symbol": symbol,
                "side": intent.side,
                "mode": intent.mode,
            },
        )

    def _record_blocked_attempt(
        self,
        *,
        intent: PaperOrderIntent,
        symbol: str,
        requested_price: Decimal | None,
        reason: str,
        metadata: dict,
    ) -> ExecutionAttempt | None:
        if self.attempt_service is None:
            return None
        return self.attempt_service.record(
            bot_id=intent.bot_id,
            strategy_id=intent.strategy_id,
            symbol=symbol,
            side=intent.side,
            mode=intent.mode,
            broker="paper",
            requested_quantity=intent.quantity,
            requested_price=requested_price,
            decision_reason=intent.decision_reason,
            risk_status="allowed",
            safety_status=reason,
            final_status="blocked_by_safety",
            final_reason=reason,
            metadata=metadata,
        )

    def _finalize_attempt(
        self,
        attempt: ExecutionAttempt | None,
        *,
        final_status: str,
        final_reason: str,
        order_id: int | None = None,
        safety_status: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        if attempt is None or self.attempt_service is None:
            return
        self.attempt_service.mark_final(
            attempt,
            final_status=final_status,
            final_reason=final_reason,
            order_id=order_id,
            safety_status=safety_status,
            metadata=metadata,
        )

    def _get_latest_price(self, symbol: str) -> Decimal | None:
        latest = self.market_data_service.get_latest(symbol)
        if latest is None or not isinstance(latest, MarketEvent):
            return None
        return latest.price or latest.close

    def _apply_slippage(self, price: Decimal, side: str) -> Decimal:
        slippage_multiplier = self.slippage_bps / BPS_DIVISOR
        if side == "buy":
            return price * (Decimal("1") + slippage_multiplier)
        return price * (Decimal("1") - slippage_multiplier)

    def _calculate_fee(self, notional: Decimal) -> Decimal:
        return notional * (self.fee_bps / BPS_DIVISOR)

    def _uses_draft_balance(self, intent: PaperOrderIntent) -> bool:
        if intent.bot_id is None:
            return False
        return BotRepository(self.repository.db).get_by_id(intent.bot_id) is not None

    def _draft_balance_service(self) -> DraftBalanceService:
        return DraftBalanceService(
            DraftBalanceRepository(self.repository.db),
            BotRepository(self.repository.db),
            autocommit=False,
        )

    def _paper_position_service(self) -> PaperPositionService:
        return PaperPositionService(
            PaperPositionRepository(self.repository.db),
            autocommit=False,
        )

    def _paper_equity_snapshot_service(self) -> PaperEquitySnapshotService:
        return PaperEquitySnapshotService(
            PaperEquitySnapshotRepository(self.repository.db),
            DraftBalanceRepository(self.repository.db),
            PaperPositionRepository(self.repository.db),
            self.market_data_service,
        )

    @staticmethod
    def _symbol_assets(symbol: str) -> tuple[str, str]:
        normalized = symbol.strip().upper()
        for quote_asset in QUOTE_ASSET_SUFFIXES:
            if normalized.endswith(quote_asset) and len(normalized) > len(quote_asset):
                return normalized[: -len(quote_asset)], quote_asset
        return normalized, "USDT"

    @staticmethod
    def _build_broker_result(result: ExecutionResult) -> BrokerOrderResult:
        fill = result.fill
        order = result.order
        return BrokerOrderResult(
            accepted=result.accepted,
            status=result.status,
            message=result.message,
            order_id=order.id if order is not None else None,
            executed_quantity=fill.fill_quantity if fill is not None else None,
            executed_price=fill.fill_price if fill is not None else None,
            fee=fill.fee if fill is not None else None,
            reason=order.rejection_reason if not result.accepted and order is not None else result.message if not result.accepted else None,
            metadata={
                "broker": "paper",
                "symbol": order.symbol if order is not None else None,
                "side": order.side if order is not None else None,
                "mode": order.mode if order is not None else None,
                "fill_id": fill.id if fill is not None else None,
                "attempt_id": result.execution_attempt.id if result.execution_attempt is not None else None,
            },
        )

    @staticmethod
    def _validate_intent(intent: PaperOrderIntent) -> str | None:
        if not intent.symbol or not intent.symbol.strip():
            return "Symbol must not be empty"
        if intent.side not in {"buy", "sell"}:
            return "Order side must be buy or sell"
        if intent.order_type != "market":
            return "Only market paper orders are supported"
        if not intent.quantity.is_finite() or intent.quantity <= ZERO:
            return "Order quantity must be a positive number"
        return None


class SimulatedExecutionService(PaperExecutionService):
    pass


class PaperExecutionBroker:
    def __init__(
        self,
        execution_service: PaperExecutionService,
        safety_guard: ExecutionSafetyGuard | None = None,
        attempt_service: ExecutionAttemptService | None = None,
    ):
        self.execution_service = execution_service
        self.safety_guard = safety_guard or execution_service.safety_guard or ExecutionSafetyGuard()
        self.attempt_service = attempt_service
        self.execution_service.safety_guard = self.safety_guard
        if self.execution_service.safety_guard.daily_limit_service is None:
            self.execution_service.safety_guard.daily_limit_service = ExecutionDailyLimitService(
                ExecutionAttemptRepository(self.execution_service.repository.db)
            )
        if self.attempt_service is not None:
            self.execution_service.attempt_service = self.attempt_service
            self.execution_service.safety_rejections_create_order = False

    def submit_market_order(self, intent: BrokerOrderIntent) -> BrokerOrderResult:
        safety_decision = self.safety_guard.validate_order(intent, broker="paper")
        if not safety_decision.allowed:
            if self.attempt_service is not None:
                self.attempt_service.record(
                    bot_id=intent.bot_id,
                    strategy_id=intent.strategy_id,
                    symbol=intent.symbol,
                    side=intent.side,
                    mode=intent.mode,
                    broker="paper",
                    requested_quantity=intent.quantity,
                    requested_price=None,
                    decision_reason=intent.decision_reason,
                    risk_status=None,
                    safety_status=safety_decision.reason,
                    final_status="blocked_by_safety",
                    final_reason=safety_decision.reason,
                    metadata=safety_decision.metadata,
                )
            return BrokerOrderResult(
                accepted=False,
                status="rejected",
                message=safety_decision.reason,
                reason=safety_decision.reason,
                metadata=safety_decision.metadata,
            )
        result = self.execution_service.submit_broker_order(intent)
        if self.attempt_service is not None and result.metadata.get("attempt_id") is None:
            self.attempt_service.record(
                bot_id=intent.bot_id,
                strategy_id=intent.strategy_id,
                symbol=intent.symbol,
                side=intent.side,
                mode=intent.mode,
                broker="paper",
                requested_quantity=intent.quantity,
                requested_price=result.executed_price,
                decision_reason=intent.decision_reason,
                risk_status="allowed",
                safety_status="allowed",
                final_status="filled" if result.accepted else "rejected_by_broker",
                final_reason=result.reason or result.message,
                order_id=result.order_id,
                metadata=result.metadata,
            )
        return result
