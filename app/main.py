from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import log_requests
from app.db.session import SessionLocal
from app.engine.bot_runner import BotRunner, RunnerConfig
from app.repositories.portfolio import PortfolioRepository
from app.services.market_data_service import MarketDataService
from app.services.portfolio_account import PortfolioAccountService

configure_logging()
logger = get_logger(__name__)
settings = get_settings()
ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    market_data_service = getattr(app.state, "market_data_service", None)
    if market_data_service is None:
        market_data_service = MarketDataService.from_settings(settings)
        app.state.market_data_service = market_data_service
    session_factory = getattr(app.state, "db_session_factory", SessionLocal)
    bot_runner = getattr(app.state, "bot_runner", None)
    if bot_runner is None:
        bot_runner = BotRunner(
            session_factory=session_factory,
            market_data_service=market_data_service,
            config=RunnerConfig(
                enabled=settings.bot_runner_enabled,
                poll_interval_seconds=settings.bot_runner_poll_interval_seconds,
                simulation_enabled=settings.simulation_enabled,
                simulation_fee_bps=settings.simulation_fee_bps,
                simulation_slippage_bps=settings.simulation_slippage_bps,
            ),
        )
        app.state.bot_runner = bot_runner

    logger.info(
        "application_startup",
        extra={"service": settings.app_name, "environment": settings.environment},
    )
    with session_factory() as db:
        PortfolioAccountService(PortfolioRepository(db)).ensure_account(
            base_currency=settings.simulation_base_currency,
            starting_cash=settings.simulation_starting_cash,
        )
    await market_data_service.start()
    await bot_runner.start()
    yield
    await bot_runner.stop()
    await market_data_service.stop()
    logger.info("application_shutdown", extra={"service": settings.app_name})


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

register_exception_handlers(app)
app.middleware("http")(log_requests)
app.include_router(api_router)

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/dashboard", tags=["frontend"])
async def dashboard() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
