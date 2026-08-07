"""Celery task that transcribes a saved audio file with a local Vosk model.

The model is loaded once per worker process and reused for every task.
"""

import asyncio
import json
import os
import wave

from celery import shared_task
from vosk import KaldiRecognizer, Model

from app.core.config import settings
from app.db.base import async_session
from app.models import Recording
from app.schemas import RecordingStatus


_model: Model | None = None


def get_model() -> Model:
    """Load the Vosk model once and cache it."""
    global _model
    if _model is None:
        if not os.path.exists(settings.VOSK_MODEL_PATH):
            raise RuntimeError(f"Vosk model not found at {settings.VOSK_MODEL_PATH}")
        _model = Model(settings.VOSK_MODEL_PATH)
    return _model


def transcribe_audio(audio_path: str) -> tuple[str, float]:
    """Transcribe a 16-bit mono PCM WAV file and return (text, duration)."""
    wf = wave.open(audio_path, "rb")
    if (
        wf.getnchannels() != 1
        or wf.getsampwidth() != 2
        or wf.getcomptype() != "NONE"
    ):
        raise ValueError("Audio must be WAV mono 16-bit PCM")

    frame_rate = wf.getframerate()
    n_frames = wf.getnframes()
    duration = n_frames / float(frame_rate) if frame_rate else 0.0

    model = get_model()
    recognizer = KaldiRecognizer(model, frame_rate)
    recognizer.SetWords(False)

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        recognizer.AcceptWaveform(data)

    result = json.loads(recognizer.FinalResult())
    wf.close()
    return result.get("text", "").strip(), duration


async def _update_recording(
    recording_id: str,
    status: str,
    transcript: str | None = None,
    duration_seconds: float | None = None,
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
            if duration_seconds is not None:
                recording.duration_seconds = duration_seconds
            if error_message is not None:
                recording.error_message = error_message


@shared_task(bind=True, max_retries=3)
def process_recording(self, recording_id: str, audio_path: str) -> None:
    try:
        asyncio.run(
            _update_recording(recording_id, RecordingStatus.PROCESSING.value)
        )
        transcript, duration = transcribe_audio(audio_path)
        asyncio.run(
            _update_recording(
                recording_id,
                RecordingStatus.COMPLETED.value,
                transcript=transcript,
                duration_seconds=duration,
            )
        )
    except Exception as exc:
        asyncio.run(
            _update_recording(
                recording_id,
                RecordingStatus.FAILED.value,
                error_message=str(exc),
            )
        )
        raise self.retry(exc=exc, countdown=10)
