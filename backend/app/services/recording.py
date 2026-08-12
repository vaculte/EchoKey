"""Recording lifecycle: save upload, enqueue transcription, list/delete history."""

import os
import uuid
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Recording
from app.schemas import RecordingStatus
from app.tasks.transcribe import process_recording


async def create_recording(
    file_content: bytes, filename: str, db: AsyncSession
) -> Recording:
    recording_id = str(uuid.uuid4())
    ext = Path(filename).suffix.lower() or ".wav"
    relative_path = f"{recording_id}{ext}"
    full_path = os.path.join(settings.AUDIO_UPLOAD_DIR, relative_path)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(file_content)

    recording = Recording(
        id=recording_id,
        status=RecordingStatus.PENDING.value,
        audio_path=full_path,
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    process_recording.delay(recording_id, full_path)
    return recording


async def get_recording(db: AsyncSession, recording_id: str) -> Recording | None:
    return await db.get(Recording, recording_id)


async def list_recordings(db: AsyncSession, limit: int = 20) -> list[Recording]:
    result = await db.execute(
        select(Recording)
        .order_by(desc(Recording.created_at))
        .limit(limit)
    )
    return result.scalars().all()


async def delete_recording(db: AsyncSession, recording_id: str) -> bool:
    recording = await get_recording(db, recording_id)
    if recording is None:
        return False

    if os.path.exists(recording.audio_path):
        os.remove(recording.audio_path)

    await db.delete(recording)
    await db.commit()
    return True
