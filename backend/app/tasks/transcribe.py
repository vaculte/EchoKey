"""Celery task that transcribes a saved audio file.

This is currently a stub: it updates the recording status and writes a placeholder transcript.
Real Vosk integration will be added in the worker layer.
"""

from celery import shared_task

from app.db.base import async_session
from app.models import Recording
from app.schemas import RecordingStatus


async def _update_recording(
    recording_id: str,
    status: str,
    transcript: str | None = None,
    error_message: str | None = None,
) -> None:
    async with async_session() as session:
        async with session.begin():
            recording = await session.get(Recording, recording_id)
            if recording is None:
                return
            recording.status = status
            if transcript is not None:
                recording.transcript = transcript
            if error_message is not None:
                recording.error_message = error_message


@shared_task(bind=True, max_retries=3)
def process_recording(self, recording_id: str, audio_path: str) -> None:
    try:
        # Mark as processing.
        # TODO: replace placeholder with Vosk transcription.
        import asyncio

        asyncio.run(_update_recording(recording_id, RecordingStatus.PROCESSING.value))
        asyncio.run(
            _update_recording(
                recording_id,
                RecordingStatus.COMPLETED.value,
                transcript="transcription placeholder",
            )
        )
    except Exception as exc:
        import asyncio

        asyncio.run(
            _update_recording(
                recording_id,
                RecordingStatus.FAILED.value,
                error_message=str(exc),
            )
        )
        raise self.retry(exc=exc, countdown=10)
