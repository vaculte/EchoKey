"""Tests for liveness and readiness endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import health as health_module
from app.db.base import get_db
from app.main import app


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def health_client(monkeypatch):
    db_session = AsyncMock()

    async def override_get_db():
        yield db_session

    monkeypatch.setattr(health_module, "_check_redis", AsyncMock(return_value=True))
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_health_is_liveness_endpoint(health_client, monkeypatch):
    database_check = AsyncMock(return_value=False)
    redis_check = AsyncMock(return_value=False)
    monkeypatch.setattr(health_module, "_check_database", database_check)
    monkeypatch.setattr(health_module, "_check_redis", redis_check)

    response = await health_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    database_check.assert_not_awaited()
    redis_check.assert_not_awaited()


async def test_ready_ok(health_client):
    response = await health_client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": True, "redis": True}


async def test_ready_returns_503_when_database_is_unavailable(
    health_client, monkeypatch
):
    monkeypatch.setattr(health_module, "_check_database", AsyncMock(return_value=False))

    response = await health_client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": False,
        "redis": True,
    }


async def test_ready_returns_503_when_redis_is_unavailable(health_client, monkeypatch):
    monkeypatch.setattr(health_module, "_check_redis", AsyncMock(return_value=False))

    response = await health_client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": True,
        "redis": False,
    }
