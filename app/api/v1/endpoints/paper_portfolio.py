from fastapi import APIRouter

from app.api.dependencies import DbSession, MarketDataServiceDep
from app.repositories.portfolio import PortfolioRepository
from app.schemas.portfolio import PaperPortfolioResetRead, PaperPortfolioResetRequest, PaperPortfolioSnapshotRead
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/paper-portfolio")


@router.get("", response_model=PaperPortfolioSnapshotRead)
async def get_paper_portfolio(
    db: DbSession,
    market_data_service: MarketDataServiceDep,
) -> PaperPortfolioSnapshotRead:
    service = PortfolioService(PortfolioRepository(db), market_data_service)
    return service.get_paper_snapshot()


@router.post("/reset", response_model=PaperPortfolioResetRead)
async def reset_paper_portfolio(
    payload: PaperPortfolioResetRequest,
    db: DbSession,
    market_data_service: MarketDataServiceDep,
) -> PaperPortfolioResetRead:
    service = PortfolioService(PortfolioRepository(db), market_data_service)
    return service.reset_paper_portfolio(payload.starting_balance)
