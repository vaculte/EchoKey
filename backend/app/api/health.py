"""Health check endpoint for liveness and readiness probes."""

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db
from app.schemas import HealthResponse

router = APIRouter()


async def _check_redis() -> bool:
    try:
        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await client.ping()
        await client.close()
        return True
    except Exception:
        return False


@router.get("", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)):
    database_ok = False
    try:
        await db.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        pass

    redis_ok = await _check_redis()
    status = "ok" if database_ok and redis_ok else "degraded"
    return HealthResponse(status=status, database=database_ok, redis=redis_ok)
