"""Pydantic schemas for API responses and enums."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class RecordingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RecordingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    audio_path: str
    duration_seconds: float | None
    transcript: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    database: bool
    redis: bool
