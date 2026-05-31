from fastapi import APIRouter

from app.api.dependencies import DbSession, MarketDataServiceDep
from app.core.config import get_settings
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_accounting import PaperAccountingRepository
from app.repositories.portfolio import PortfolioRepository
from app.schemas.execution import MarketOrderRequest, MarketOrderResponse, SimulatedFillRead, SimulatedOrderRead
from app.services.brokers.safety import ExecutionSafetyConfig, ExecutionSafetyGuard
from app.services.execution_attempt import ExecutionAttemptService
from app.services.execution_limits import ExecutionDailyLimitService
from app.services.simulated_execution import SimulatedExecutionService

router = APIRouter(prefix="/execution")
settings = get_settings()


@router.get("/orders", response_model=list[SimulatedOrderRead])
async def list_orders(db: DbSession) -> list[SimulatedOrderRead]:
    repository = PortfolioRepository(db)
    return [SimulatedOrderRead.model_validate(order) for order in repository.list_orders()]


@router.get("/fills", response_model=list[SimulatedFillRead])
async def list_fills(db: DbSession) -> list[SimulatedFillRead]:
    repository = PortfolioRepository(db)
    return [SimulatedFillRead.model_validate(fill) for fill in repository.list_fills()]


@router.post("/market-order", response_model=MarketOrderResponse)
async def create_market_order(
    payload: MarketOrderRequest,
    db: DbSession,
    market_data_service: MarketDataServiceDep,
) -> MarketOrderResponse:
    service = SimulatedExecutionService(
        repository=PortfolioRepository(db),
        market_data_service=market_data_service,
        simulation_enabled=settings.simulation_enabled,
        fee_bps=settings.simulation_fee_bps,
        slippage_bps=settings.simulation_slippage_bps,
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db)),
        safety_guard=ExecutionSafetyGuard(
            ExecutionSafetyConfig(
                global_enabled=settings.execution_global_enabled,
                live_enabled=settings.execution_live_enabled,
                testnet_order_submission_enabled=settings.binance_testnet_order_submission_enabled,
                max_order_notional=settings.execution_max_order_notional,
                max_daily_order_count=settings.execution_max_daily_order_count,
                max_daily_loss=settings.execution_max_daily_loss,
            ),
            daily_limit_service=ExecutionDailyLimitService(
                ExecutionAttemptRepository(db),
                paper_accounting_repository=PaperAccountingRepository(db),
            ),
        ),
    )
    result = service.submit_market_order(payload)
    return MarketOrderResponse(
        accepted=result.accepted,
        status=result.status,
        message=result.message,
        order=SimulatedOrderRead.model_validate(result.order),
        fill=SimulatedFillRead.model_validate(result.fill) if result.fill is not None else None,
        updated_cash_balance=result.updated_cash_balance,
        position=service.build_position_snapshot(result.position),
    )
