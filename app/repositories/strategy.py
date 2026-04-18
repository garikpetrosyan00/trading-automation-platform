from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.strategy import Strategy


class StrategyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, strategy: Strategy) -> Strategy:
        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)
        return strategy

    def get_by_id(self, strategy_id: int) -> Strategy | None:
        statement = select(Strategy).where(Strategy.id == strategy_id)
        return self.db.scalar(statement)

    def list_all(self) -> list[Strategy]:
        statement = select(Strategy).order_by(Strategy.created_at.desc(), Strategy.id.desc())
        return list(self.db.scalars(statement).all())

    def update(self, strategy: Strategy) -> Strategy:
        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)
        return strategy

    def delete(self, strategy: Strategy) -> None:
        self.db.delete(strategy)
        self.db.commit()
