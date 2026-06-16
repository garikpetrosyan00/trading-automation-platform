from fastapi import APIRouter

from app.api.dependencies import DbSession
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.schemas.draft_balance import DraftBalanceAssetRead, DraftBalanceRead, decimal_to_string
from app.services.draft_balance import DraftBalanceService, DraftBalanceSnapshot

router = APIRouter()


@router.get("/bots/{bot_id}/draft-balance", response_model=DraftBalanceRead)
async def get_bot_draft_balance(bot_id: int, db: DbSession) -> DraftBalanceRead:
    service = _service(db)
    return _to_read(service.get_bot_draft_balance(bot_id))


@router.post("/bots/{bot_id}/draft-balance/reset", response_model=DraftBalanceRead)
async def reset_bot_draft_balance(bot_id: int, db: DbSession) -> DraftBalanceRead:
    service = _service(db)
    return _to_read(service.reset_bot_draft_balance(bot_id))


def _service(db) -> DraftBalanceService:
    return DraftBalanceService(
        DraftBalanceRepository(db),
        BotRepository(db),
    )


def _to_read(snapshot: DraftBalanceSnapshot) -> DraftBalanceRead:
    return DraftBalanceRead(
        bot_id=snapshot.bot_id,
        assets=[
            DraftBalanceAssetRead(
                asset=asset.asset,
                available=decimal_to_string(asset.available),
                locked=decimal_to_string(asset.locked),
                total=decimal_to_string(asset.total),
            )
            for asset in snapshot.assets
        ],
    )
