import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import ToneLayerRequest


class AudioJobCreate(BaseModel):
    project_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    mode: AudioMode = AudioMode.SINE
    channels: ChannelMode = ChannelMode.MONO
    frequency_hz: float | None = Field(default=432.0, gt=0, le=20000)
    left_frequency_hz: float | None = Field(default=None, gt=0, le=20000)
    right_frequency_hz: float | None = Field(default=None, gt=0, le=20000)
    pulse_frequency_hz: float | None = Field(default=None, gt=0, le=100)
    modulation_depth: float = Field(default=1.0, ge=0, le=1.0)
    layers: list[ToneLayerRequest] = Field(default_factory=list, max_length=16)
    preset_name: str | None = Field(default=None, max_length=100)
    duration_seconds: int = Field(gt=0, le=3600)
    sample_rate: int = Field(default=44100, ge=8000, le=192000)
    amplitude: float = Field(default=0.2, gt=0, le=1.0)
    fade_in_seconds: float = Field(default=0.1, ge=0, le=60)
    fade_out_seconds: float = Field(default=0.1, ge=0, le=60)
    seamless_loop: bool = False
    loop_crossfade_seconds: float = Field(default=0.25, ge=0, le=30)
    seed: int | None = None

    @model_validator(mode="after")
    def validate_mode_configuration(self) -> "AudioJobCreate":
        if self.mode == AudioMode.BINAURAL_BEATS:
            if self.channels != ChannelMode.STEREO:
                raise ValueError("binaural_beats requires stereo output")
            if self.left_frequency_hz is None or self.right_frequency_hz is None:
                raise ValueError("binaural frequencies are required")

        if self.mode == AudioMode.ISOCHRONIC_TONES:
            if self.frequency_hz is None or self.pulse_frequency_hz is None:
                raise ValueError("isochronic carrier and pulse frequencies are required")

        return self


class AudioJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    mode: str
    channels: str
    frequency_hz: float | None
    left_frequency_hz: float | None
    right_frequency_hz: float | None
    pulse_frequency_hz: float | None
    modulation_depth: float
    preset_name: str | None
    duration_seconds: int
    sample_rate: int
    amplitude: float
    fade_in_seconds: float
    fade_out_seconds: float
    seamless_loop: bool
    loop_crossfade_seconds: float
    seed: int | None
    status: str
    output_file_path: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
