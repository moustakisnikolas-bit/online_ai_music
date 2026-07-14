import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.audio.types import AudioMode
from app.schemas.audio import ToneLayerRequest


class AudioJobCreate(BaseModel):
    project_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    mode: AudioMode = AudioMode.SINE
    frequency_hz: float | None = Field(default=432.0, gt=0, le=20000)
    layers: list[ToneLayerRequest] = Field(default_factory=list, max_length=16)
    preset_name: str | None = Field(default=None, max_length=100)
    duration_seconds: int = Field(gt=0, le=3600)
    sample_rate: int = Field(default=44100, ge=8000, le=192000)
    amplitude: float = Field(default=0.2, gt=0, le=1.0)
    fade_in_seconds: float = Field(default=0.1, ge=0, le=60)
    fade_out_seconds: float = Field(default=0.1, ge=0, le=60)
    seed: int | None = None


class AudioJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    mode: str
    frequency_hz: float | None
    preset_name: str | None
    duration_seconds: int
    sample_rate: int
    amplitude: float
    fade_in_seconds: float
    fade_out_seconds: float
    seed: int | None
    status: str
    output_file_path: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
