from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import DbSession
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.schemas.paper_equity import PaperEquitySnapshotItemRead, PaperEquitySnapshotListRead
from app.schemas.paper_equity_summary import PaperEquitySummaryRead
from app.schemas.paper_position import decimal_to_string
from app.services.paper_equity_snapshot import PaperEquitySnapshotService
from app.services.paper_equity_summary import PaperEquitySummaryService

router = APIRouter()


@router.get("/bots/{bot_id}/paper/equity-summary", response_model=PaperEquitySummaryRead)
async def get_bot_paper_equity_summary(bot_id: int, db: DbSession) -> PaperEquitySummaryRead:
    bot = BotRepository(db).get_by_id(bot_id)
    if bot is None:
        raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

    summary = PaperEquitySummaryService(
        settings=get_settings(),
        draft_balance_repository=DraftBalanceRepository(db),
        paper_position_repository=PaperPositionRepository(db),
        paper_equity_snapshot_repository=PaperEquitySnapshotRepository(db),
    ).get_summary(bot=bot)
    return PaperEquitySummaryRead(**asdict(summary))


@router.get("/bots/{bot_id}/paper-equity", response_model=PaperEquitySnapshotListRead)
async def get_bot_paper_equity(
    bot_id: int,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> PaperEquitySnapshotListRead:
    snapshot_list = PaperEquitySnapshotService(
        PaperEquitySnapshotRepository(db),
        DraftBalanceRepository(db),
        PaperPositionRepository(db),
        bot_repository=BotRepository(db),
    ).list_bot_snapshots(bot_id, limit=limit)
    return PaperEquitySnapshotListRead(
        bot_id=snapshot_list.bot_id,
        count=len(snapshot_list.items),
        items=[
            PaperEquitySnapshotItemRead(
                id=item.id,
                bot_id=item.bot_id,
                symbol=item.symbol,
                quote_asset=item.quote_asset,
                cash_available=decimal_to_string(item.cash_available),
                cash_locked=decimal_to_string(item.cash_locked),
                base_quantity=decimal_to_string(item.base_quantity),
                base_locked=decimal_to_string(item.base_locked),
                average_entry_price=decimal_to_string(item.average_entry_price),
                realized_pnl=decimal_to_string(item.realized_pnl),
                market_price=decimal_to_string(item.market_price) if item.market_price is not None else None,
                position_value=decimal_to_string(item.position_value) if item.position_value is not None else None,
                total_equity=decimal_to_string(item.total_equity) if item.total_equity is not None else None,
                event_type=item.event_type,
                created_at=item.created_at,
            )
            for item in snapshot_list.items
        ],
    )
