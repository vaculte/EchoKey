"""Tests for the recordings API."""

import io

import pytest

from tests.conftest import make_wav_bytes


pytestmark = pytest.mark.asyncio


async def test_create_recording(client):
    data = make_wav_bytes()
    response = await client.post(
        "/recordings",
        files={"file": ("test.wav", io.BytesIO(data), "audio/wav")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["id"]
    assert body["transcript"] is None


async def test_get_recording(client):
    data = make_wav_bytes()
    create_response = await client.post(
        "/recordings",
        files={"file": ("test.wav", io.BytesIO(data), "audio/wav")},
    )
    rid = create_response.json()["id"]

    response = await client.get(f"/recordings/{rid}")
    assert response.status_code == 200
    assert response.json()["id"] == rid


async def test_get_recording_not_found(client):
    response = await client.get("/recordings/non-existent-id")
    assert response.status_code == 404


async def test_list_recordings(client):
    data = make_wav_bytes()
    await client.post(
        "/recordings",
        files={"file": ("test.wav", io.BytesIO(data), "audio/wav")},
    )
    response = await client.get("/recordings")
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_delete_recording(client):
    data = make_wav_bytes()
    create_response = await client.post(
        "/recordings",
        files={"file": ("test.wav", io.BytesIO(data), "audio/wav")},
    )
    rid = create_response.json()["id"]

    response = await client.delete(f"/recordings/{rid}")
    assert response.status_code == 204

    response = await client.get(f"/recordings/{rid}")
    assert response.status_code == 404
