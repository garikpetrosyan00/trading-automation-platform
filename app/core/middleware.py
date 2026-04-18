import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.core.logging import get_logger

logger = get_logger(__name__)


async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

    logger.info(
        "request_completed",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
