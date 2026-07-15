import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrackRatingCreate(BaseModel):
    stress_before: int | None = Field(default=None, ge=1, le=10)
    stress_after: int | None = Field(default=None, ge=1, le=10)
    mood_before: int | None = Field(default=None, ge=1, le=10)
    mood_after: int | None = Field(default=None, ge=1, le=10)
    sleep_onset_minutes: int | None = Field(default=None, ge=0, le=600)
    completed_listen: bool | None = None
    skipped_at_seconds: int | None = Field(default=None, ge=0)
    preferred_instruments: list[str] = Field(default_factory=list, max_length=50)
    uncomfortable_sounds: list[str] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)


class TrackRatingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    audio_job_id: uuid.UUID
    stress_before: int | None
    stress_after: int | None
    mood_before: int | None
    mood_after: int | None
    sleep_onset_minutes: int | None
    completed_listen: bool | None
    skipped_at_seconds: int | None
    preferred_instruments: list[str]
    uncomfortable_sounds: list[str]
    notes: str | None
    created_at: datetime
