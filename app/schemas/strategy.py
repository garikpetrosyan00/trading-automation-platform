from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrategyBase(BaseModel):
    name: NonEmptyStr
    description: str | None = None
    symbol: NonEmptyStr
    timeframe: NonEmptyStr
    is_active: bool = True


class StrategyCreate(StrategyBase):
    pass


class StrategyUpdate(BaseModel):
    name: NonEmptyStr | None = None
    description: str | None = None
    symbol: NonEmptyStr | None = None
    timeframe: NonEmptyStr | None = None
    is_active: bool | None = None


class StrategyRead(StrategyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
