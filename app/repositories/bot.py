from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bot import Bot


class BotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, bot: Bot) -> Bot:
        self.db.add(bot)
        self.db.commit()
        self.db.refresh(bot)
        return bot

    def get_by_id(self, bot_id: int) -> Bot | None:
        statement = select(Bot).where(Bot.id == bot_id)
        return self.db.scalar(statement)

    def list_all(self, strategy_id: int | None = None, status: str | None = None) -> list[Bot]:
        statement = select(Bot)

        if strategy_id is not None:
            statement = statement.where(Bot.strategy_id == strategy_id)
        if status is not None:
            statement = statement.where(Bot.status == status)

        statement = statement.order_by(Bot.created_at.desc(), Bot.id.desc())
        return list(self.db.scalars(statement).all())

    def update(self, bot: Bot) -> Bot:
        self.db.add(bot)
        self.db.commit()
        self.db.refresh(bot)
        return bot

    def delete(self, bot: Bot) -> None:
        self.db.delete(bot)
        self.db.commit()
