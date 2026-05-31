from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.portfolio_account import PortfolioAccount
from app.models.position import Position
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder


class PortfolioRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_account(self) -> PortfolioAccount | None:
        statement = select(PortfolioAccount).order_by(PortfolioAccount.id.asc()).limit(1)
        return self.db.scalar(statement)

    def create_account(self, base_currency: str, starting_cash) -> PortfolioAccount:
        account = PortfolioAccount(
            base_currency=base_currency,
            starting_cash=starting_cash,
            cash_balance=starting_cash,
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def get_position_by_symbol(self, symbol: str) -> Position | None:
        statement = select(Position).where(Position.symbol == symbol.upper())
        return self.db.scalar(statement)

    def list_positions(self, include_closed: bool = False) -> list[Position]:
        statement = select(Position).order_by(Position.symbol.asc())
        if not include_closed:
            statement = statement.where(Position.quantity > 0)
        return list(self.db.scalars(statement).all())

    def has_open_positions(self) -> bool:
        statement = select(func.count()).select_from(Position).where(Position.quantity != 0)
        return int(self.db.scalar(statement) or 0) > 0

    def reset_account(self, account: PortfolioAccount, starting_cash: Decimal) -> PortfolioAccount:
        account.starting_cash = starting_cash
        account.cash_balance = starting_cash
        self.db.add(account)
        return account

    def reset_position_session_state(self) -> None:
        positions = self.list_positions(include_closed=True)
        for position in positions:
            position.realized_pnl = Decimal("0")
            if position.quantity == 0:
                position.average_entry_price = Decimal("0")
            self.db.add(position)

    def list_orders(self) -> list[SimulatedOrder]:
        statement = select(SimulatedOrder).order_by(SimulatedOrder.created_at.desc(), SimulatedOrder.id.desc())
        return list(self.db.scalars(statement).all())

    def list_orders_filtered(
        self,
        *,
        bot_id: int | None = None,
        strategy_id: int | None = None,
        symbol: str | None = None,
        status: str | None = None,
        side: str | None = None,
        mode: str | None = None,
        limit: int = 50,
    ) -> list[SimulatedOrder]:
        statement = select(SimulatedOrder)
        if bot_id is not None:
            statement = statement.where(SimulatedOrder.bot_id == bot_id)
        if strategy_id is not None:
            statement = statement.where(SimulatedOrder.strategy_id == strategy_id)
        if symbol is not None:
            statement = statement.where(SimulatedOrder.symbol == symbol.upper())
        if status is not None:
            statement = statement.where(SimulatedOrder.status == status)
        if side is not None:
            statement = statement.where(SimulatedOrder.side == side)
        if mode is not None:
            statement = statement.where(SimulatedOrder.mode == mode)
        statement = statement.order_by(SimulatedOrder.created_at.desc(), SimulatedOrder.id.desc()).limit(limit)
        return list(self.db.scalars(statement).all())

    def get_order_by_id(self, order_id: int) -> SimulatedOrder | None:
        statement = select(SimulatedOrder).where(SimulatedOrder.id == order_id)
        return self.db.scalar(statement)

    def list_fills(self) -> list[SimulatedFill]:
        statement = select(SimulatedFill).order_by(SimulatedFill.created_at.desc(), SimulatedFill.id.desc())
        return list(self.db.scalars(statement).all())

    def list_fills_for_order(self, order_id: int) -> list[SimulatedFill]:
        statement = (
            select(SimulatedFill)
            .where(SimulatedFill.order_id == order_id)
            .order_by(SimulatedFill.filled_at.desc(), SimulatedFill.id.desc())
        )
        return list(self.db.scalars(statement).all())

    def count_fills_for_order(self, order_id: int) -> int:
        statement = select(func.count()).select_from(SimulatedFill).where(SimulatedFill.order_id == order_id)
        return int(self.db.scalar(statement) or 0)

    def get_fill_by_id(self, fill_id: int) -> SimulatedFill | None:
        statement = select(SimulatedFill).where(SimulatedFill.id == fill_id)
        return self.db.scalar(statement)

    def save(self, instance) -> None:
        self.db.add(instance)

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance) -> None:
        self.db.refresh(instance)
