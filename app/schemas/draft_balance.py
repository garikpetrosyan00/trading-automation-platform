from decimal import Decimal

from pydantic import BaseModel


class DraftBalanceAssetRead(BaseModel):
    asset: str
    available: str
    locked: str
    total: str


class DraftBalanceRead(BaseModel):
    bot_id: int
    assets: list[DraftBalanceAssetRead]


def decimal_to_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")
