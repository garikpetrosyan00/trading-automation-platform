from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.data.schemas import MarketEvent
from app.models.position import Position
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.portfolio import PortfolioRepository
from app.schemas.execution import ExecutionPositionSnapshot, MarketOrderRequest

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


class SimulatedExecutionService:
    def __init__(
        self,
        repository: PortfolioRepository,
        market_data_service,
        simulation_enabled: bool,
        fee_bps: Decimal,
        slippage_bps: Decimal,
    ):
        self.repository = repository
        self.market_data_service = market_data_service
        self.simulation_enabled = simulation_enabled
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

    def submit_market_order(self, payload: MarketOrderRequest) -> ExecutionResult:
        account = self.repository.get_account()
        if account is None:
            raise ValueError("Portfolio account is not initialized")

        latest_price = self._get_latest_price(payload.symbol)
        position = self.repository.get_position_by_symbol(payload.symbol)

        if not self.simulation_enabled:
            return self._reject_order(
                symbol=payload.symbol,
                side=payload.side,
                quantity=payload.quantity,
                requested_price_snapshot=latest_price,
                reason="Simulation is disabled",
                cash_balance=account.cash_balance,
                position=position,
            )

        if latest_price is None:
            return self._reject_order(
                symbol=payload.symbol,
                side=payload.side,
                quantity=payload.quantity,
                requested_price_snapshot=None,
                reason=f"No latest market price available for symbol {payload.symbol}",
                cash_balance=account.cash_balance,
                position=position,
            )

        fill_price = self._apply_slippage(latest_price, payload.side)
        notional = payload.quantity * fill_price
        fee = self._calculate_fee(notional)

        try:
            if payload.side == "buy":
                total_cost = notional + fee
                if total_cost > account.cash_balance:
                    return self._reject_order(
                        symbol=payload.symbol,
                        side=payload.side,
                        quantity=payload.quantity,
                        requested_price_snapshot=latest_price,
                        reason="Insufficient cash balance for this buy order",
                        cash_balance=account.cash_balance,
                        position=position,
                    )

                order = self._create_order(payload, latest_price, status="filled")
                fill = self._create_fill(order, payload, fill_price, fee)
                account.cash_balance -= total_cost

                if position is None:
                    position = Position(
                        symbol=payload.symbol,
                        quantity=ZERO,
                        average_entry_price=ZERO,
                        realized_pnl=ZERO,
                    )
                    self.repository.save(position)

                existing_cost_basis = position.quantity * position.average_entry_price
                new_total_quantity = position.quantity + payload.quantity
                new_total_cost_basis = existing_cost_basis + total_cost
                position.quantity = new_total_quantity
                position.average_entry_price = new_total_cost_basis / new_total_quantity

                self.repository.commit()
                self.repository.refresh(order)
                self.repository.refresh(fill)
                self.repository.refresh(account)
                self.repository.refresh(position)
                return ExecutionResult(
                    accepted=True,
                    status="filled",
                    message="Market buy order filled",
                    order=order,
                    fill=fill,
                    updated_cash_balance=account.cash_balance,
                    position=position,
                )

            if position is None or position.quantity < payload.quantity:
                return self._reject_order(
                    symbol=payload.symbol,
                    side=payload.side,
                    quantity=payload.quantity,
                    requested_price_snapshot=latest_price,
                    reason="Insufficient position quantity for this sell order",
                    cash_balance=account.cash_balance,
                    position=position,
                )

            order = self._create_order(payload, latest_price, status="filled")
            fill = self._create_fill(order, payload, fill_price, fee)
            proceeds = notional - fee
            cost_basis = position.average_entry_price * payload.quantity
            position.realized_pnl += proceeds - cost_basis
            position.quantity -= payload.quantity
            if position.quantity == ZERO:
                position.average_entry_price = ZERO
            account.cash_balance += proceeds

            self.repository.commit()
            self.repository.refresh(order)
            self.repository.refresh(fill)
            self.repository.refresh(account)
            self.repository.refresh(position)
            return ExecutionResult(
                accepted=True,
                status="filled",
                message="Market sell order filled",
                order=order,
                fill=fill,
                updated_cash_balance=account.cash_balance,
                position=position,
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
        symbol: str,
        side: str,
        quantity: Decimal,
        requested_price_snapshot: Decimal | None,
        reason: str,
        cash_balance: Decimal,
        position: Position | None,
    ) -> ExecutionResult:
        try:
            order = SimulatedOrder(
                symbol=symbol,
                side=side,
                quantity=quantity,
                requested_price_snapshot=requested_price_snapshot,
                status="rejected",
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

    def _create_order(self, payload: MarketOrderRequest, latest_price: Decimal, status: str) -> SimulatedOrder:
        order = SimulatedOrder(
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            requested_price_snapshot=latest_price,
            status=status,
        )
        self.repository.save(order)
        self.repository.flush()
        return order

    def _create_fill(
        self,
        order: SimulatedOrder,
        payload: MarketOrderRequest,
        fill_price: Decimal,
        fee: Decimal,
    ) -> SimulatedFill:
        fill = SimulatedFill(
            order_id=order.id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            fill_price=fill_price,
            fee=fee,
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
