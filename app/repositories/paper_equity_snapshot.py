from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.paper_equity_snapshot import PaperEquitySnapshot


class PaperEquitySnapshotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, snapshot: PaperEquitySnapshot) -> PaperEquitySnapshot:
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def list_latest_for_bot(
        self,
        *,
        bot_id: int,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[PaperEquitySnapshot]:
        statement = select(PaperEquitySnapshot).where(PaperEquitySnapshot.bot_id == bot_id)
        if symbol is not None:
            statement = statement.where(PaperEquitySnapshot.symbol == symbol)
        statement = statement.order_by(
            PaperEquitySnapshot.created_at.desc(),
            PaperEquitySnapshot.id.desc(),
        ).limit(limit)
        return list(self.db.scalars(statement).all())

    def count_for_bot(self, *, bot_id: int) -> int:
        statement = select(func.count()).select_from(PaperEquitySnapshot).where(PaperEquitySnapshot.bot_id == bot_id)
        return int(self.db.scalar(statement) or 0)
