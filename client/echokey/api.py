"""HTTP client for the EchoKey backend API."""

import time

import httpx

from echokey.config import settings


class EchoKeyClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.ECHOKEY_API_URL).rstrip("/")

    def upload(self, audio_path: str) -> str:
        with httpx.Client(timeout=60.0) as client:
            with open(audio_path, "rb") as f:
                response = client.post(
                    f"{self.base_url}/recordings",
                    files={"file": ("recording.wav", f, "audio/wav")},
                )
                response.raise_for_status()
                data = response.json()
                return data["id"]

    def poll(self, recording_id: str, interval: float = 0.5, timeout: float = 30.0) -> str | None:
        start = time.time()
        with httpx.Client(timeout=10.0) as client:
            while time.time() - start < timeout:
                response = client.get(f"{self.base_url}/recordings/{recording_id}")
                response.raise_for_status()
                data = response.json()
                if data["status"] == "completed":
                    return data.get("transcript")
                if data["status"] == "failed":
                    return None
                time.sleep(interval)
        return None
