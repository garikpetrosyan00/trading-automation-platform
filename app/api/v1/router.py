from fastapi import APIRouter

from app.api.v1.endpoints.bots import router as bots_router
from app.api.v1.endpoints.bot_runs import router as bot_runs_router
from app.api.v1.endpoints.execution_profiles import router as execution_profiles_router
from app.api.v1.endpoints.system import router as system_router
from app.api.v1.endpoints.strategies import router as strategies_router

router = APIRouter()
router.include_router(system_router, prefix="/system", tags=["system"])
router.include_router(strategies_router, prefix="/strategies", tags=["strategies"])
router.include_router(bots_router, prefix="/bots", tags=["bots"])
router.include_router(execution_profiles_router, prefix="/bots/{bot_id}", tags=["execution-profiles"])
router.include_router(bot_runs_router, prefix="/bots/{bot_id}", tags=["bot-runs"])
