from fastapi import APIRouter

from app.api.v1.endpoints.alert_events import router as alert_events_router
from app.api.v1.endpoints.alert_rules import router as alert_rules_router
from app.api.v1.endpoints.backtests import router as backtests_router
from app.api.v1.endpoints.bots import router as bots_router
from app.api.v1.endpoints.bot_runtime import router as bot_runtime_router
from app.api.v1.endpoints.bot_runs import router as bot_runs_router
from app.api.v1.endpoints.draft_balance import router as draft_balance_router
from app.api.v1.endpoints.execution import router as execution_router
from app.api.v1.endpoints.execution_safety import router as execution_safety_router
from app.api.v1.endpoints.market import router as market_router
from app.api.v1.endpoints.execution_profiles import router as execution_profiles_router
from app.api.v1.endpoints.local_backtest_artifacts import router as local_backtest_artifacts_router
from app.api.v1.endpoints.market_data import router as market_data_router
from app.api.v1.endpoints.notification_rules import router as notification_rules_router
from app.api.v1.endpoints.orders import router as orders_router
from app.api.v1.endpoints.paper_equity import router as paper_equity_router
from app.api.v1.endpoints.paper_portfolio import router as paper_portfolio_router
from app.api.v1.endpoints.paper_position import router as paper_position_router
from app.api.v1.endpoints.portfolio import router as portfolio_router
from app.api.v1.endpoints.run_events import router as run_events_router
from app.api.v1.endpoints.system import router as system_router
from app.api.v1.endpoints.strategies import router as strategies_router

router = APIRouter()
router.include_router(system_router, prefix="/system", tags=["system"])
router.include_router(market_data_router, tags=["market-data"])
router.include_router(portfolio_router, tags=["portfolio"])
router.include_router(paper_portfolio_router, tags=["paper-portfolio"])
router.include_router(execution_router, tags=["execution"])
router.include_router(execution_safety_router, tags=["execution-safety"])
router.include_router(draft_balance_router, tags=["draft-balance"])
router.include_router(paper_position_router, tags=["paper-position"])
router.include_router(paper_equity_router, tags=["paper-equity"])
router.include_router(orders_router, tags=["orders"])
router.include_router(market_router, tags=["market"])
router.include_router(backtests_router, prefix="/backtests", tags=["backtests"])
router.include_router(local_backtest_artifacts_router, prefix="/backtests", tags=["backtests"])
router.include_router(bot_runtime_router, tags=["bot-runtime"])
router.include_router(strategies_router, prefix="/strategies", tags=["strategies"])
router.include_router(bots_router, prefix="/bots", tags=["bots"])
router.include_router(alert_events_router, tags=["alert-events"])
router.include_router(alert_rules_router, tags=["alert-rules"])
router.include_router(execution_profiles_router, prefix="/bots/{bot_id}", tags=["execution-profiles"])
router.include_router(bot_runs_router, prefix="/bots/{bot_id}", tags=["bot-runs"])
router.include_router(run_events_router, prefix="/bots/{bot_id}/runs/{run_id}", tags=["run-events"])
router.include_router(notification_rules_router, tags=["notification-rules"])
