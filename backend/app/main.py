"""FastAPI application entrypoint."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.AUDIO_UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(
    title="EchoKey Backend",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health.router, prefix="/health", tags=["health"])
