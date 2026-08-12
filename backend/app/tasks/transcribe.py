"""Celery task that transcribes a saved audio file with a local Vosk model."""

import asyncio
import json
import os
import wave
from pathlib import Path

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from vosk import KaldiRecognizer, Model

from app.core.config import settings
from app.models import Recording
from app.schemas import RecordingStatus


_model: Model | None = None


def _resolve_model_path() -> str:
    """Resolve the Vosk model path relative to the project root.

    Use it only when the configured path is not absolute.
    """
    configured = Path(settings.VOSK_MODEL_PATH).expanduser()
    if configured.is_absolute():
        return str(configured)
    # backend/app/tasks/transcribe.py -> project root
    project_root = Path(__file__).resolve().parents[3]
    return str(project_root / configured)


def get_model() -> Model:
    """Load the Vosk model once and cache it."""
    global _model
    if _model is None:
        model_path = _resolve_model_path()
        if not os.path.exists(model_path):
            raise RuntimeError(f"Vosk model not found at {model_path}")
        _model = Model(model_path)
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


async def _update_task(
    recording_id: str,
    status: str,
    transcript: str | None = None,
    duration_seconds: float | None = None,
    error_message: str | None = None,
) -> None:
    """Create a fresh async engine per task.

    This avoids event-loop issues in forked workers.
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    try:
        async with session_factory() as session:
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
    finally:
        await engine.dispose()


async def _run(recording_id: str, audio_path: str) -> None:
    await _update_task(recording_id, RecordingStatus.PROCESSING.value)
    try:
        transcript, duration = transcribe_audio(audio_path)
        await _update_task(
            recording_id,
            RecordingStatus.COMPLETED.value,
            transcript=transcript,
            duration_seconds=duration,
        )
    except Exception as exc:
        await _update_task(
            recording_id,
            RecordingStatus.FAILED.value,
            error_message=str(exc),
        )
        raise


@shared_task(bind=True, max_retries=3)
def process_recording(self, recording_id: str, audio_path: str) -> None:
    try:
        asyncio.run(_run(recording_id, audio_path))
    except RuntimeError as exc:
        # Non-retryable errors such as a missing Vosk model: record failure and stop.
        asyncio.run(
            _update_task(
                recording_id,
                RecordingStatus.FAILED.value,
                error_message=str(exc),
            )
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)
