from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.paper_position import PaperPosition


class PaperPositionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_bot_symbol(self, *, bot_id: int, symbol: str) -> PaperPosition | None:
        statement = select(PaperPosition).where(
            PaperPosition.bot_id == bot_id,
            PaperPosition.symbol == symbol,
        )
        return self.db.scalar(statement)

    def get_for_bot_symbol_for_update(self, *, bot_id: int, symbol: str) -> PaperPosition | None:
        statement = (
            select(PaperPosition)
            .where(
                PaperPosition.bot_id == bot_id,
                PaperPosition.symbol == symbol,
            )
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_or_create_for_bot_symbol_for_update(
        self,
        *,
        bot_id: int,
        symbol: str,
        base_asset: str,
        quote_asset: str,
    ) -> PaperPosition:
        position = self.get_for_bot_symbol_for_update(bot_id=bot_id, symbol=symbol)
        if position is not None:
            return position

        position = PaperPosition(
            bot_id=bot_id,
            symbol=symbol,
            base_asset=base_asset,
            quote_asset=quote_asset,
            quantity=Decimal("0"),
            average_entry_price=Decimal("0"),
            realized_pnl=Decimal("0"),
        )
        self.db.add(position)
        self.db.flush()
        return position

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, instance) -> None:
        self.db.refresh(instance)
