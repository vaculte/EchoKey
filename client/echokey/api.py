"""HTTP client for the EchoKey backend API."""

import logging
import time

import httpx

from echokey.config import settings

logger = logging.getLogger(__name__)


class EchoKeyClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.ECHOKEY_API_URL).rstrip("/")

    def upload(self, audio_path: str) -> str:
        logger.info("Uploading %s to %s", audio_path, self.base_url)
        with httpx.Client(timeout=60.0) as client:
            with open(audio_path, "rb") as f:
                response = client.post(
                    f"{self.base_url}/recordings",
                    files={"file": ("recording.wav", f, "audio/wav")},
                )
                logger.info(
                    "Upload response: %s %s", response.status_code, response.text[:200]
                )
                response.raise_for_status()
                data = response.json()
                return data["id"]

    def poll(
        self,
        recording_id: str,
        interval: float = 0.5,
        timeout: float = 30.0,
    ) -> str | None:
        logger.info("Polling transcription for %s", recording_id)
        start = time.time()
        with httpx.Client(timeout=10.0) as client:
            while time.time() - start < timeout:
                response = client.get(f"{self.base_url}/recordings/{recording_id}")
                logger.info(
                    "Poll response: %s %s", response.status_code, response.text[:200]
                )
                response.raise_for_status()
                data = response.json()
                if data["status"] == "completed":
                    return data.get("transcript")
                if data["status"] == "failed":
                    logger.error(
                        "Transcription failed on server: %s",
                        data.get("error_message"),
                    )
                    return None
                time.sleep(interval)
        logger.warning("Polling timeout for %s", recording_id)
        return None
