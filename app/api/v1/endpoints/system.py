from fastapi import APIRouter

from app.schemas.system import PingResponse
from app.services.system import SystemService

router = APIRouter()


@router.get("/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    return PingResponse(message=SystemService.ping())
