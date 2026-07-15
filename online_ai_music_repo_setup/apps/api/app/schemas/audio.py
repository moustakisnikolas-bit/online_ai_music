from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.audio.types import AudioMode, ChannelMode, OutputFormat, TextureMode


class ToneLayerRequest(BaseModel):
    frequency_hz: float = Field(gt=0, le=20000)
    amplitude: float = Field(gt=0, le=1.0)


class AmbientNoiseLayer(BaseModel):
    kind: Literal["noise"] = "noise"
    noise_type: AudioMode
    gain: float = Field(gt=0, le=1.0)

    @field_validator("noise_type")
    @classmethod
    def _validate_noise_type(cls, value: AudioMode) -> AudioMode:
        if value not in {
            AudioMode.WHITE_NOISE,
            AudioMode.PINK_NOISE,
            AudioMode.BROWN_NOISE,
        }:
            raise ValueError(
                "noise_type must be white_noise, pink_noise or brown_noise"
            )
        return value


class AmbientToneLayer(BaseModel):
    kind: Literal["tone"] = "tone"
    frequency_hz: float = Field(gt=0, le=20000)
    gain: float = Field(gt=0, le=1.0)


class AmbientTextureLayer(BaseModel):
    kind: Literal["texture"] = "texture"
    texture_type: TextureMode
    gain: float = Field(gt=0, le=1.0)

    @field_validator("texture_type")
    @classmethod
    def _validate_texture_type(cls, value: TextureMode) -> TextureMode:
        if value == TextureMode.NONE:
            raise ValueError("texture_type must be rain, wind, waves or birds")
        return value


class AmbientSampleLayer(BaseModel):
    kind: Literal["sample"] = "sample"
    sample_id: str = Field(min_length=1, max_length=100)
    gain: float = Field(gt=0, le=1.0)


AmbientLayerRequest = Annotated[
    AmbientNoiseLayer | AmbientToneLayer | AmbientTextureLayer | AmbientSampleLayer,
    Field(discriminator="kind"),
]


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
    output_format: OutputFormat = OutputFormat.WAV
    ambient_layers: list[AmbientLayerRequest] = Field(
        default_factory=list, max_length=16
    )
    long_form: bool = False
    chunk_frames: int = Field(default=65536, ge=1024, le=1048576)

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

        if self.mode == AudioMode.MIXED_AMBIENT and not self.ambient_layers:
            raise ValueError(
                "mixed_ambient requires at least one entry in ambient_layers"
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
    output_format: str
    file_path: str

    @computed_field
    @property
    def filename(self) -> str:
        return Path(self.file_path).name
