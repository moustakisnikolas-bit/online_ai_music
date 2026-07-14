from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.audio.types import AudioMode, ChannelMode


class ToneLayerRequest(BaseModel):
    frequency_hz: float = Field(gt=0, le=20000)
    amplitude: float = Field(gt=0, le=1.0)


class AudioGenerationRequest(BaseModel):
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
    def validate_mode_configuration(self) -> "AudioGenerationRequest":
        if self.mode == AudioMode.LAYERED_TONES and not self.layers:
            raise ValueError("layers are required for layered_tones mode")

        if self.mode == AudioMode.PRESET and not self.preset_name:
            raise ValueError("preset_name is required for preset mode")

        if self.mode == AudioMode.BINAURAL_BEATS:
            if self.channels != ChannelMode.STEREO:
                raise ValueError("binaural_beats requires stereo output")
            if self.left_frequency_hz is None or self.right_frequency_hz is None:
                raise ValueError(
                    "left_frequency_hz and right_frequency_hz are required "
                    "for binaural_beats"
                )

        if self.mode == AudioMode.ISOCHRONIC_TONES:
            if self.frequency_hz is None or self.pulse_frequency_hz is None:
                raise ValueError(
                    "frequency_hz and pulse_frequency_hz are required "
                    "for isochronic_tones"
                )

        if self.fade_in_seconds + self.fade_out_seconds > self.duration_seconds:
            raise ValueError("combined fades cannot exceed total duration")

        if self.seamless_loop and self.loop_crossfade_seconds * 2 > self.duration_seconds:
            raise ValueError("loop crossfade is too long for the requested duration")

        return self


class AudioGenerationResponse(BaseModel):
    id: str
    title: str
    mode: str
    channels: str
    frequency_hz: float | None = None
    duration_seconds: int
    sample_rate: int
    status: str
    file_path: str

    @property
    def filename(self) -> str:
        return Path(self.file_path).name
