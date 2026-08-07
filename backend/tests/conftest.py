"""Shared test fixtures and helpers."""

import io
import os
import wave
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://echokey:echokey@localhost:5432/echokey_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("AUDIO_UPLOAD_DIR", "uploads/test")

from app.api import health as health_module
from app.core.config import settings
from app.db.base import Base, get_db
from app.main import app


pytest_plugins = ("pytest_asyncio",)


def make_wav_bytes(seconds: float = 0.5) -> bytes:
    """Generate a silent mono 16-bit PCM WAV buffer."""
    buf = io.BytesIO()
    n = int(16000 * seconds)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * n)
    return buf.getvalue()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with session_factory() as session:
        yield session
        await session.execute(text("DELETE FROM recordings"))
        await session.commit()


@pytest.fixture
async def redis_ok(monkeypatch):
    monkeypatch.setattr(health_module, "_check_redis", AsyncMock(return_value=True))


@pytest.fixture
def no_celery(monkeypatch):
    monkeypatch.setattr(
        "app.services.recording.process_recording",
        MagicMock(),
    )


@pytest.fixture
async def client(db_session, redis_ok, no_celery):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app, raise_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
