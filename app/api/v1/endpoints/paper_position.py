from fastapi import APIRouter

from app.api.dependencies import DbSession, MarketDataServiceDep
from app.repositories.bot import BotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.schemas.paper_position import PaperPositionRead, decimal_to_string
from app.services.paper_position import PaperPositionService

router = APIRouter()


@router.get("/bots/{bot_id}/paper-position", response_model=PaperPositionRead)
async def get_bot_paper_position(
    bot_id: int,
    db: DbSession,
    market_data_service: MarketDataServiceDep,
) -> PaperPositionRead:
    snapshot = PaperPositionService(
        PaperPositionRepository(db),
        bot_repository=BotRepository(db),
        market_data_service=market_data_service,
    ).get_bot_position_snapshot(bot_id)
    return PaperPositionRead(
        bot_id=snapshot.bot_id,
        symbol=snapshot.symbol,
        base_asset=snapshot.base_asset,
        quote_asset=snapshot.quote_asset,
        quantity=decimal_to_string(snapshot.quantity),
        average_entry_price=decimal_to_string(snapshot.average_entry_price),
        realized_pnl=decimal_to_string(snapshot.realized_pnl),
        market_price=decimal_to_string(snapshot.market_price) if snapshot.market_price is not None else None,
        unrealized_pnl=decimal_to_string(snapshot.unrealized_pnl) if snapshot.unrealized_pnl is not None else None,
        position_value=decimal_to_string(snapshot.position_value) if snapshot.position_value is not None else None,
        updated_at=snapshot.updated_at,
    )
