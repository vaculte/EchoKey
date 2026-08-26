"""Liveness and readiness endpoints for Kubernetes probes."""

import redis.asyncio as redis
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.core.config import settings
from app.db.base import get_db
from app.schemas import LivenessResponse, ReadinessResponse

router = APIRouter()


async def _check_redis() -> bool:
    try:
        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await client.ping()
        await client.close()
        return True
    except Exception:
        return False


async def _check_database(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/health", response_model=LivenessResponse)
async def health() -> LivenessResponse:
    """Report whether the FastAPI process can answer requests."""
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def ready(db: AsyncSession = Depends(get_db)) -> ReadinessResponse | JSONResponse:
    """Report whether required PostgreSQL and Redis dependencies are available."""
    database_ok = await _check_database(db)

    redis_ok = await _check_redis()
    response = ReadinessResponse(
        status="ok" if database_ok and redis_ok else "degraded",
        database=database_ok,
        redis=redis_ok,
    )
    if response.status == "ok":
        return response
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=response.model_dump(),
    )
