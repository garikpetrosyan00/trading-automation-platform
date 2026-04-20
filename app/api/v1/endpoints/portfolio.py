from fastapi import APIRouter

from app.api.dependencies import DbSession, MarketDataServiceDep
from app.repositories.portfolio import PortfolioRepository
from app.schemas.portfolio import PortfolioSummaryRead, PositionRead
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/portfolio")


@router.get("/summary", response_model=PortfolioSummaryRead)
async def get_portfolio_summary(db: DbSession, market_data_service: MarketDataServiceDep) -> PortfolioSummaryRead:
    service = PortfolioService(PortfolioRepository(db), market_data_service)
    return service.get_summary()


@router.get("/positions", response_model=list[PositionRead])
async def get_portfolio_positions(db: DbSession, market_data_service: MarketDataServiceDep) -> list[PositionRead]:
    service = PortfolioService(PortfolioRepository(db), market_data_service)
    return service.list_positions()
