from fastapi import APIRouter

from app.api.v1.endpoints.system import router as system_router
from app.api.v1.endpoints.strategies import router as strategies_router

router = APIRouter()
router.include_router(system_router, prefix="/system", tags=["system"])
router.include_router(strategies_router, prefix="/strategies", tags=["strategies"])
