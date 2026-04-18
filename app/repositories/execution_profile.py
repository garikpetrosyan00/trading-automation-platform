from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution_profile import ExecutionProfile


class ExecutionProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, execution_profile: ExecutionProfile) -> ExecutionProfile:
        self.db.add(execution_profile)
        self.db.commit()
        self.db.refresh(execution_profile)
        return execution_profile

    def get_by_bot_id(self, bot_id: int) -> ExecutionProfile | None:
        statement = select(ExecutionProfile).where(ExecutionProfile.bot_id == bot_id)
        return self.db.scalar(statement)

    def update(self, execution_profile: ExecutionProfile) -> ExecutionProfile:
        self.db.add(execution_profile)
        self.db.commit()
        self.db.refresh(execution_profile)
        return execution_profile

    def delete(self, execution_profile: ExecutionProfile) -> None:
        self.db.delete(execution_profile)
        self.db.commit()
