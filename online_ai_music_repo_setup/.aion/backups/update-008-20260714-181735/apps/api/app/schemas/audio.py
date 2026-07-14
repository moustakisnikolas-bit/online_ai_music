from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class AudioGenerationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    frequency_hz: float = Field(gt=0, le=20000)
    duration_seconds: int = Field(gt=0, le=600)
    sample_rate: int = Field(default=44100, ge=8000, le=192000)
    amplitude: float = Field(default=0.2, gt=0, le=1.0)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return " ".join(value.strip().split())


class AudioGenerationResponse(BaseModel):
    id: str
    title: str
    frequency_hz: float
    duration_seconds: int
    sample_rate: int
    status: str
    file_path: str

    @property
    def filename(self) -> str:
        return Path(self.file_path).name
