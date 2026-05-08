from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backtest_run import BacktestRun


class BacktestRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, backtest_run: BacktestRun) -> BacktestRun:
        self.db.add(backtest_run)
        self.db.commit()
        self.db.refresh(backtest_run)
        return backtest_run

    def list_recent(self, *, strategy_id: int | None = None, limit: int = 50) -> list[BacktestRun]:
        statement = select(BacktestRun)
        if strategy_id is not None:
            statement = statement.where(BacktestRun.strategy_id == strategy_id)
        statement = statement.order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc()).limit(limit)
        return list(self.db.scalars(statement).all())
