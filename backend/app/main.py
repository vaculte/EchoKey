"""FastAPI application entrypoint."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api import health, recordings
from app.celery_app import celery_app  # noqa: F401  # load Celery app before API uses tasks
from app.core.config import settings
from app.db.base import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    os.makedirs(settings.AUDIO_UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(
    title="EchoKey Backend",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(recordings.router, prefix="/recordings", tags=["recordings"])


@app.get("/metrics", tags=["monitoring"])
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
