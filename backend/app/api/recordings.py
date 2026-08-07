"""REST API endpoints for recording uploads, status, history, and deletion."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.schemas import RecordingResponse
from app.services.recording import (
    create_recording,
    delete_recording,
    get_recording,
    list_recordings,
)

router = APIRouter()


@router.post("", response_model=RecordingResponse, status_code=201)
async def upload_recording(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    return await create_recording(
        content,
        file.filename or "recording.wav",
        db,
    )


@router.get("/{recording_id}", response_model=RecordingResponse)
async def retrieve_recording(
    recording_id: str,
    db: AsyncSession = Depends(get_db),
):
    recording = await get_recording(db, recording_id)
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording


@router.get("", response_model=list[RecordingResponse])
async def retrieve_recordings(db: AsyncSession = Depends(get_db)):
    return await list_recordings(db)


@router.delete("/{recording_id}", status_code=204)
async def remove_recording(
    recording_id: str,
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_recording(db, recording_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recording not found")
    return None
