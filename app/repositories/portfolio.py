from sqlalchemy import select
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

    def list_orders(self) -> list[SimulatedOrder]:
        statement = select(SimulatedOrder).order_by(SimulatedOrder.created_at.desc(), SimulatedOrder.id.desc())
        return list(self.db.scalars(statement).all())

    def list_fills(self) -> list[SimulatedFill]:
        statement = select(SimulatedFill).order_by(SimulatedFill.created_at.desc(), SimulatedFill.id.desc())
        return list(self.db.scalars(statement).all())

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
