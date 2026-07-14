import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AudioJobCreate(BaseModel):
    project_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    frequency_hz: float = Field(gt=0, le=20000)
    duration_seconds: int = Field(gt=0, le=3600)
    sample_rate: int = Field(default=44100, ge=8000, le=192000)
    amplitude: float = Field(default=0.2, gt=0, le=1.0)


class AudioJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    frequency_hz: float
    duration_seconds: int
    sample_rate: int
    amplitude: float
    status: str
    output_file_path: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
