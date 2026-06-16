from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.draft_balance import DraftBalance


class DraftBalanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_bot(self, bot_id: int) -> list[DraftBalance]:
        statement = (
            select(DraftBalance)
            .where(DraftBalance.bot_id == bot_id)
            .order_by(DraftBalance.asset.asc(), DraftBalance.id.asc())
        )
        return list(self.db.scalars(statement).all())

    def get_for_bot_asset(self, *, bot_id: int, asset: str) -> DraftBalance | None:
        statement = select(DraftBalance).where(DraftBalance.bot_id == bot_id, DraftBalance.asset == asset)
        return self.db.scalar(statement)

    def get_for_bot_asset_for_update(self, *, bot_id: int, asset: str) -> DraftBalance | None:
        statement = (
            select(DraftBalance)
            .where(DraftBalance.bot_id == bot_id, DraftBalance.asset == asset)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_or_create_for_bot_asset_for_update(self, *, bot_id: int, asset: str) -> DraftBalance:
        row = self.get_for_bot_asset_for_update(bot_id=bot_id, asset=asset)
        if row is not None:
            return row
        row = DraftBalance(bot_id=bot_id, asset=asset, available=Decimal("0"), locked=Decimal("0"))
        self.db.add(row)
        self.db.flush()
        return row

    def upsert_for_bot_asset(
        self,
        *,
        bot_id: int,
        asset: str,
        available: Decimal,
        locked: Decimal,
    ) -> DraftBalance:
        row = self.get_for_bot_asset(bot_id=bot_id, asset=asset)
        if row is None:
            row = DraftBalance(bot_id=bot_id, asset=asset, available=available, locked=locked)
        else:
            row.available = available
            row.locked = locked
        self.db.add(row)
        self.db.flush()
        return row

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, instance) -> None:
        self.db.refresh(instance)
