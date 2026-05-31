from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.data.schemas import MarketEvent
from app.models.position import Position
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.portfolio import PortfolioRepository
from app.schemas.execution import ExecutionPositionSnapshot, MarketOrderRequest
from app.services.brokers.base import BrokerOrderIntent, BrokerOrderResult
from app.services.brokers.safety import ExecutionSafetyGuard
from app.services.execution_attempt import ExecutionAttemptService
from app.services.paper_portfolio import PaperPortfolioService

ZERO = Decimal("0")
BPS_DIVISOR = Decimal("10000")


@dataclass
class ExecutionResult:
    accepted: bool
    status: str
    message: str
    order: SimulatedOrder
    fill: SimulatedFill | None
    updated_cash_balance: Decimal
    position: Position | None


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
    ):
        self.repository = repository
        self.market_data_service = market_data_service
        self.simulation_enabled = simulation_enabled
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.safety_guard = safety_guard or ExecutionSafetyGuard()

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

        safety_decision = self.safety_guard.validate_order(intent, broker="paper", market_price=latest_price)
        if not safety_decision.allowed:
            return self._reject_order(
                intent=intent,
                symbol=symbol,
                requested_price_snapshot=latest_price,
                reason=safety_decision.reason,
                cash_balance=account.cash_balance,
                position=position,
            )

        fill_price = self._apply_slippage(latest_price, intent.side)
        notional = intent.quantity * fill_price
        fee = self._calculate_fee(notional)

        try:
            if intent.side == "buy":
                required_cash = notional + fee
                if required_cash > account.cash_balance:
                    return self._reject_order(
                        intent=intent,
                        symbol=symbol,
                        requested_price_snapshot=latest_price,
                        reason="insufficient_paper_cash",
                        cash_balance=account.cash_balance,
                        position=position,
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
            )
        except Exception:
            self.repository.rollback()
            raise

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
        return fill

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

    @staticmethod
    def _build_broker_result(result: ExecutionResult) -> BrokerOrderResult:
        fill = result.fill
        return BrokerOrderResult(
            accepted=result.accepted,
            status=result.status,
            message=result.message,
            order_id=result.order.id,
            executed_quantity=fill.fill_quantity if fill is not None else None,
            executed_price=fill.fill_price if fill is not None else None,
            fee=fill.fee if fill is not None else None,
            reason=result.order.rejection_reason if not result.accepted else None,
            metadata={
                "broker": "paper",
                "symbol": result.order.symbol,
                "side": result.order.side,
                "mode": result.order.mode,
                "fill_id": fill.id if fill is not None else None,
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
        self.safety_guard = safety_guard or ExecutionSafetyGuard()
        self.attempt_service = attempt_service

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
        if self.attempt_service is not None:
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
