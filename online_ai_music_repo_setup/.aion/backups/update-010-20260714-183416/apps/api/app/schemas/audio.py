from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.audio.types import AudioMode


class ToneLayerRequest(BaseModel):
    frequency_hz: float = Field(gt=0, le=20000)
    amplitude: float = Field(gt=0, le=1.0)


class AudioGenerationRequest(BaseModel):
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

    @model_validator(mode="after")
    def validate_mode_configuration(self) -> "AudioGenerationRequest":
        if self.mode == AudioMode.LAYERED_TONES and not self.layers:
            raise ValueError("layers are required for layered_tones mode")

        if self.mode == AudioMode.PRESET and not self.preset_name:
            raise ValueError("preset_name is required for preset mode")

        if self.fade_in_seconds + self.fade_out_seconds > self.duration_seconds:
            raise ValueError("combined fades cannot exceed total duration")

        return self


class AudioGenerationResponse(BaseModel):
    id: str
    title: str
    mode: str
    frequency_hz: float | None = None
    duration_seconds: int
    sample_rate: int
    status: str
    file_path: str

    @property
    def filename(self) -> str:
        return Path(self.file_path).name
