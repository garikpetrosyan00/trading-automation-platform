from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.portfolio_account import PortfolioAccount
from app.models.paper_accounting_event import PaperAccountingEvent
from app.models.position import Position
from app.models.simulated_fill import SimulatedFill
from app.repositories.portfolio import PortfolioRepository

ZERO = Decimal("0")


@dataclass
class PaperPortfolioResult:
    accepted: bool
    message: str
    account: PortfolioAccount
    position: Position | None
    realized_pnl_delta: Decimal = ZERO


class PaperPortfolioService:
    def __init__(self, repository: PortfolioRepository):
        self.repository = repository

    def apply_fill(self, fill: SimulatedFill) -> PaperPortfolioResult:
        account = self.repository.get_account()
        if account is None:
            raise ValueError("Portfolio account is not initialized")

        position = self.repository.get_position_by_symbol(fill.symbol)
        quantity = fill.fill_quantity if fill.fill_quantity is not None else fill.quantity
        invalid_reason = self._validate_fill(fill, quantity)
        if invalid_reason is not None:
            return PaperPortfolioResult(
                accepted=False,
                message=invalid_reason,
                account=account,
                position=position,
            )

        if fill.side == "buy":
            return self._apply_buy_fill(account, position, fill, quantity)
        if fill.side == "sell":
            return self._apply_sell_fill(account, position, fill, quantity)

        return PaperPortfolioResult(
            accepted=False,
            message="Fill side must be buy or sell",
            account=account,
            position=position,
        )

    def _apply_buy_fill(
        self,
        account: PortfolioAccount,
        position: Position | None,
        fill: SimulatedFill,
        quantity: Decimal,
    ) -> PaperPortfolioResult:
        total_cost = (quantity * fill.fill_price) + fill.fee
        if total_cost > account.cash_balance:
            return PaperPortfolioResult(
                accepted=False,
                message="insufficient_paper_cash",
                account=account,
                position=position,
            )

        if position is None:
            position = Position(
                symbol=fill.symbol,
                quantity=ZERO,
                average_entry_price=ZERO,
                realized_pnl=ZERO,
            )
            self.repository.save(position)
            self.repository.flush()

        existing_cost_basis = position.quantity * position.average_entry_price
        new_total_quantity = position.quantity + quantity
        new_total_cost_basis = existing_cost_basis + total_cost

        account.cash_balance -= total_cost
        position.quantity = new_total_quantity
        position.average_entry_price = new_total_cost_basis / new_total_quantity
        self._record_accounting_event(
            fill=fill,
            cash_delta=-total_cost,
            realized_pnl_delta=ZERO,
        )

        return PaperPortfolioResult(
            accepted=True,
            message="Buy fill applied",
            account=account,
            position=position,
        )

    def _apply_sell_fill(
        self,
        account: PortfolioAccount,
        position: Position | None,
        fill: SimulatedFill,
        quantity: Decimal,
    ) -> PaperPortfolioResult:
        if position is None or position.quantity < quantity:
            return PaperPortfolioResult(
                accepted=False,
                message="Insufficient position quantity for this sell order",
                account=account,
                position=position,
            )

        proceeds = (quantity * fill.fill_price) - fill.fee
        cost_basis = position.average_entry_price * quantity
        realized_pnl_delta = proceeds - cost_basis

        account.cash_balance += proceeds
        position.realized_pnl += realized_pnl_delta
        position.quantity -= quantity
        if position.quantity == ZERO:
            position.average_entry_price = ZERO
        self._record_accounting_event(
            fill=fill,
            cash_delta=proceeds,
            realized_pnl_delta=realized_pnl_delta,
        )

        return PaperPortfolioResult(
            accepted=True,
            message="Sell fill applied",
            account=account,
            position=position,
            realized_pnl_delta=realized_pnl_delta,
        )

    @staticmethod
    def _validate_fill(fill: SimulatedFill, quantity: Decimal) -> str | None:
        if not quantity.is_finite() or quantity <= ZERO:
            return "Fill quantity must be a positive number"
        if not fill.fill_price.is_finite() or fill.fill_price <= ZERO:
            return "Fill price must be a positive number"
        if not fill.fee.is_finite() or fill.fee < ZERO:
            return "Fill fee must not be negative"
        return None

    def _record_accounting_event(
        self,
        *,
        fill: SimulatedFill,
        cash_delta: Decimal,
        realized_pnl_delta: Decimal,
    ) -> None:
        order = self.repository.get_order_by_id(fill.order_id)
        event = PaperAccountingEvent(
            order_id=order.id if order is not None else None,
            fill_id=fill.id,
            bot_id=order.bot_id if order is not None else None,
            strategy_id=order.strategy_id if order is not None else None,
            symbol=fill.symbol,
            side=fill.side,
            mode="paper",
            event_type="fill_applied",
            cash_delta=cash_delta,
            realized_pnl_delta=realized_pnl_delta,
        )
        self.repository.save(event)
