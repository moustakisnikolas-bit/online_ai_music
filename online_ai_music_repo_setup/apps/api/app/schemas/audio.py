from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.audio.music_theory import SCALES, parse_note_name
from app.audio.soundfont_synth import GM_INSTRUMENTS
from app.audio.types import AudioMode, ChannelMode, OutputFormat, TextureMode

SYNTH_PATTERNS = ("up", "down", "up_down", "random")


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
            raise ValueError(
                "texture_type must be one of: rain, wind, waves, birds, "
                "fire, water, thunder, chimes, deep_waterfall, "
                "distant_thunder, airplane_cabin"
            )
        return value


class AmbientSampleLayer(BaseModel):
    kind: Literal["sample"] = "sample"
    sample_id: str = Field(min_length=1, max_length=100)
    gain: float = Field(gt=0, le=1.0)


class AmbientSynthLayer(BaseModel):
    # A melody line inside a mixed_ambient mix -- reuses the exact same
    # SoundFont-based engine and validation as top-level mode=synthesizer
    # (see synth_* fields on AudioGenerationRequest below), just as one
    # composable layer instead of the whole track.
    kind: Literal["synth"] = "synth"
    instrument: str = Field(max_length=50)
    root_note: str = Field(max_length=4)
    scale: str = Field(max_length=30)
    pattern: str = Field(max_length=10)
    note_duration_seconds: float = Field(default=0.5, gt=0, le=10)
    octave_range: int = Field(default=2, ge=1, le=4)
    attack_seconds: float = Field(default=0.05, ge=0, le=5)
    release_seconds: float = Field(default=0.3, ge=0, le=10)
    filter_cutoff: float = Field(default=0.8, ge=0, le=1.0)
    filter_resonance: float = Field(default=0.2, ge=0, le=1.0)
    gain: float = Field(gt=0, le=1.0)

    @field_validator("instrument")
    @classmethod
    def _validate_instrument(cls, value: str) -> str:
        if value not in GM_INSTRUMENTS:
            raise ValueError(f"Unknown synth instrument: {value!r}")
        return value

    @field_validator("scale")
    @classmethod
    def _validate_scale(cls, value: str) -> str:
        if value not in SCALES:
            raise ValueError(f"Unknown synth scale: {value!r}")
        return value

    @field_validator("pattern")
    @classmethod
    def _validate_pattern(cls, value: str) -> str:
        if value not in SYNTH_PATTERNS:
            raise ValueError(f"Unknown synth pattern: {value!r}")
        return value

    @field_validator("root_note")
    @classmethod
    def _validate_root_note(cls, value: str) -> str:
        parse_note_name(value)
        return value


AmbientLayerRequest = Annotated[
    AmbientNoiseLayer
    | AmbientToneLayer
    | AmbientTextureLayer
    | AmbientSampleLayer
    | AmbientSynthLayer,
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

    # Synthesizer mode (SoundFont-based instrument playback + a scale/
    # arpeggio pattern generator -- see audio/music_theory.py and
    # audio/soundfont_synth.py). The first four are required together when
    # mode=synthesizer; the tone-shaping controls always have real
    # defaults since they're meaningful even untouched.
    synth_instrument: str | None = Field(default=None, max_length=50)
    synth_root_note: str | None = Field(default=None, max_length=4)
    synth_scale: str | None = Field(default=None, max_length=30)
    synth_pattern: str | None = Field(default=None, max_length=10)
    synth_note_duration_seconds: float = Field(default=0.5, gt=0, le=10)
    synth_octave_range: int = Field(default=2, ge=1, le=4)
    synth_attack_seconds: float = Field(default=0.05, ge=0, le=5)
    synth_release_seconds: float = Field(default=0.3, ge=0, le=10)
    synth_filter_cutoff: float = Field(default=0.8, ge=0, le=1.0)
    synth_filter_resonance: float = Field(default=0.2, ge=0, le=1.0)

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
    # Texture beds (rain, fire, waves, ...) layered under *any* mode, not
    # just mixed_ambient -- e.g. a sine tone or binaural beat with rain
    # mixed underneath. Uses the same AmbientTextureLayer shape as
    # ambient_layers' texture entries.
    textures: list[AmbientTextureLayer] = Field(default_factory=list, max_length=8)
    long_form: bool = False
    chunk_frames: int = Field(default=65536, ge=1024, le=1048576)

    # Concert-pitch reference (A440 default, A432 alternate per the
    # production spec). Only affects chimes_texture's named pitches --
    # every other mode takes frequency_hz directly, so there's no "note"
    # to retune.
    tuning_hz: float = Field(default=440.0, gt=0, le=1000)

    # Macro energy arc over the whole track (spec section 2's "emotional
    # journey": arrival -> settling -> deep state -> resolution,
    # simplified to a 3-point envelope). Defaults to 1.0/1.0/1.0, a flat
    # no-op envelope, so existing behavior is unchanged unless requested.
    energy_start: float = Field(default=1.0, ge=0, le=1.0)
    energy_middle: float = Field(default=1.0, ge=0, le=1.0)
    energy_end: float = Field(default=1.0, ge=0, le=1.0)

    # Mastering pass (post-processing, opt-in -- nothing here changes
    # default generation behavior unless explicitly requested). See
    # audio/mastering.py.
    target_lufs: float | None = Field(default=None, ge=-40, le=0)
    true_peak_dbtp: float = Field(default=-1.0, ge=-20, le=0)
    apply_mastering_eq: bool = False
    fold_bass_to_mono: bool = False
    apply_reverb: bool = False
    reverb_decay_seconds: float = Field(default=2.5, gt=0, le=10)
    reverb_wet_level: float = Field(default=0.25, ge=0, le=1.0)

    # Breathing-sync envelope (spec section 5). Disabled by default. The
    # spec's target cycle is 8-12s total (its own example: 4s inhale, 6s
    # exhale); the 15s-per-phase bound below is a broad sanity limit, not
    # an enforcement of that target -- it's presented as a recommendation,
    # not a hard rule.
    breathing_sync_enabled: bool = False
    breathing_inhale_seconds: float = Field(default=4.0, gt=0, le=15)
    breathing_exhale_seconds: float = Field(default=6.0, gt=0, le=15)
    breathing_sync_depth: float = Field(default=0.3, ge=0, le=1.0)

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

        if self.mode == AudioMode.SYNTHESIZER:
            if not (
                self.synth_instrument
                and self.synth_root_note
                and self.synth_scale
                and self.synth_pattern
            ):
                raise ValueError(
                    "synth_instrument, synth_root_note, synth_scale, and "
                    "synth_pattern are required for synthesizer mode"
                )
            if self.synth_instrument not in GM_INSTRUMENTS:
                raise ValueError(f"Unknown synth_instrument: {self.synth_instrument!r}")
            if self.synth_scale not in SCALES:
                raise ValueError(f"Unknown synth_scale: {self.synth_scale!r}")
            if self.synth_pattern not in SYNTH_PATTERNS:
                raise ValueError(f"Unknown synth_pattern: {self.synth_pattern!r}")
            parse_note_name(self.synth_root_note)

        if self.long_form and self.mode == AudioMode.SYNTHESIZER:
            raise ValueError(
                "synthesizer mode does not support long_form=True yet "
                "(the chunked renderer doesn't model note timing or "
                "instrument state across chunks)"
            )

        if self.long_form and self.textures:
            raise ValueError(
                "textures are not yet supported with long_form=True "
                "(the chunked renderer doesn't implement layering)"
            )

        if self.long_form and (
            self.target_lufs is not None
            or self.apply_mastering_eq
            or self.fold_bass_to_mono
            or self.apply_reverb
        ):
            raise ValueError(
                "mastering options (target_lufs, apply_mastering_eq, "
                "fold_bass_to_mono, apply_reverb) are not yet supported "
                "with long_form=True (the chunked renderer writes output "
                "incrementally and can't be post-processed as one array)"
            )

        if self.fold_bass_to_mono and self.channels != ChannelMode.STEREO:
            raise ValueError("fold_bass_to_mono only applies to stereo output")

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
    # Measured on the final output regardless of whether target_lufs was
    # requested -- informational visibility even when no mastering was
    # applied. None only if the audio was silent (loudness undefined).
    loudness_lufs: float | None = None
    validation_warnings: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def filename(self) -> str:
        return Path(self.file_path).name
