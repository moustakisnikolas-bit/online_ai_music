#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-010-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

backup_file() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    local relative="${path#${TARGET}/}"
    mkdir -p "${BACKUP_DIR}/$(dirname "${relative}")"
    cp "${path}" "${BACKUP_DIR}/${relative}"
  fi
}

for file in \
  "apps/api/app/audio/types.py" \
  "apps/api/app/audio/dsp.py" \
  "apps/api/app/schemas/audio.py" \
  "apps/api/app/schemas/audio_job.py" \
  "apps/api/app/models/audio_job.py" \
  "apps/api/app/repositories/audio_jobs.py" \
  "apps/api/app/services/audio_generator.py" \
  "apps/worker/app/main.py"; do
  backup_file "${TARGET}/${file}"
done

cat > apps/api/app/audio/types.py <<'EOF'
from enum import StrEnum


class AudioMode(StrEnum):
    SINE = "sine"
    LAYERED_TONES = "layered_tones"
    WHITE_NOISE = "white_noise"
    PINK_NOISE = "pink_noise"
    BROWN_NOISE = "brown_noise"
    BINAURAL_BEATS = "binaural_beats"
    ISOCHRONIC_TONES = "isochronic_tones"
    PRESET = "preset"


class ChannelMode(StrEnum):
    MONO = "mono"
    STEREO = "stereo"
EOF

cat > apps/api/app/audio/dsp.py <<'EOF'
import math
import random
from collections.abc import Iterable


def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def normalize(samples: Iterable[float], peak: float = 0.95) -> list[float]:
    values = list(samples)
    maximum = max((abs(value) for value in values), default=0.0)

    if maximum == 0:
        return values

    scale = peak / maximum
    return [clamp(value * scale) for value in values]


def apply_fades(
    samples: list[float],
    sample_rate: int,
    fade_in_seconds: float,
    fade_out_seconds: float,
) -> list[float]:
    total = len(samples)
    fade_in_frames = min(total, max(0, int(fade_in_seconds * sample_rate)))
    fade_out_frames = min(total, max(0, int(fade_out_seconds * sample_rate)))
    result = samples[:]

    if fade_in_frames > 0:
        for index in range(fade_in_frames):
            result[index] *= index / fade_in_frames

    if fade_out_frames > 0:
        start = total - fade_out_frames
        for index in range(fade_out_frames):
            result[start + index] *= 1.0 - (index / fade_out_frames)

    return result


def apply_loop_crossfade(
    samples: list[float],
    sample_rate: int,
    crossfade_seconds: float,
) -> list[float]:
    if crossfade_seconds <= 0:
        return samples

    crossfade_frames = min(
        len(samples) // 2,
        max(1, int(crossfade_seconds * sample_rate)),
    )

    if crossfade_frames <= 0:
        return samples

    result = samples[:]

    for index in range(crossfade_frames):
        ratio = index / crossfade_frames
        start_value = result[index]
        end_index = len(result) - crossfade_frames + index
        end_value = result[end_index]
        blended = (start_value * ratio) + (end_value * (1.0 - ratio))
        result[index] = blended
        result[end_index] = blended

    return result


def generate_sine_samples(
    frequency_hz: float,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
) -> list[float]:
    frame_count = duration_seconds * sample_rate
    angular = 2.0 * math.pi * frequency_hz

    return [
        amplitude * math.sin(angular * (index / sample_rate))
        for index in range(frame_count)
    ]


def generate_layered_tones(
    layers: list[tuple[float, float]],
    duration_seconds: int,
    sample_rate: int,
) -> list[float]:
    frame_count = duration_seconds * sample_rate
    samples = [0.0] * frame_count

    for frequency_hz, amplitude in layers:
        angular = 2.0 * math.pi * frequency_hz
        for index in range(frame_count):
            samples[index] += amplitude * math.sin(angular * (index / sample_rate))

    return normalize(samples)


def generate_binaural_channels(
    left_frequency_hz: float,
    right_frequency_hz: float,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
) -> tuple[list[float], list[float]]:
    return (
        generate_sine_samples(
            left_frequency_hz,
            duration_seconds,
            sample_rate,
            amplitude,
        ),
        generate_sine_samples(
            right_frequency_hz,
            duration_seconds,
            sample_rate,
            amplitude,
        ),
    )


def generate_isochronic_samples(
    carrier_frequency_hz: float,
    pulse_frequency_hz: float,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    modulation_depth: float,
) -> list[float]:
    frame_count = duration_seconds * sample_rate
    samples: list[float] = []

    for index in range(frame_count):
        time_position = index / sample_rate
        carrier = math.sin(2.0 * math.pi * carrier_frequency_hz * time_position)
        modulation = 0.5 * (
            1.0 + math.sin(2.0 * math.pi * pulse_frequency_hz * time_position)
        )
        gain = (1.0 - modulation_depth) + (modulation_depth * modulation)
        samples.append(amplitude * gain * carrier)

    return samples


def generate_white_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> list[float]:
    generator = random.Random(seed)
    frame_count = duration_seconds * sample_rate
    return [generator.uniform(-amplitude, amplitude) for _ in range(frame_count)]


def generate_brown_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> list[float]:
    generator = random.Random(seed)
    frame_count = duration_seconds * sample_rate
    value = 0.0
    samples: list[float] = []

    for _ in range(frame_count):
        value += generator.uniform(-0.02, 0.02)
        value = clamp(value)
        samples.append(value)

    return normalize(samples, peak=amplitude)


def generate_pink_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> list[float]:
    generator = random.Random(seed)
    frame_count = duration_seconds * sample_rate
    b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
    samples: list[float] = []

    for _ in range(frame_count):
        white = generator.uniform(-1.0, 1.0)
        b0 = 0.99886 * b0 + white * 0.0555179
        b1 = 0.99332 * b1 + white * 0.0750759
        b2 = 0.96900 * b2 + white * 0.1538520
        b3 = 0.86650 * b3 + white * 0.3104856
        b4 = 0.55000 * b4 + white * 0.5329522
        b5 = -0.7616 * b5 - white * 0.0168980
        pink = b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362
        b6 = white * 0.115926
        samples.append(pink)

    return normalize(samples, peak=amplitude)
EOF

cat > apps/api/app/schemas/audio.py <<'EOF'
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
EOF

cat > apps/api/app/schemas/audio_job.py <<'EOF'
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
EOF

cat > apps/api/app/models/audio_job.py <<'EOF'
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AudioJob(Base):
    __tablename__ = "audio_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False, default="sine")
    channels: Mapped[str] = mapped_column(String(20), nullable=False, default="mono")
    frequency_hz: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_frequency_hz: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_frequency_hz: Mapped[float | None] = mapped_column(Float, nullable=True)
    pulse_frequency_hz: Mapped[float | None] = mapped_column(Float, nullable=True)
    modulation_depth: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    layers: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    preset_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=44100)
    amplitude: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    fade_in_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    fade_out_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    seamless_loop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    loop_crossfade_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued", index=True)
    output_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
EOF

cat > apps/api/app/repositories/audio_jobs.py <<'EOF'
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audio_job import AudioJob
from app.schemas.audio_job import AudioJobCreate


def create_audio_job(db: Session, payload: AudioJobCreate) -> AudioJob:
    job = AudioJob(
        project_id=payload.project_id,
        title=payload.title,
        mode=payload.mode.value,
        channels=payload.channels.value,
        frequency_hz=payload.frequency_hz,
        left_frequency_hz=payload.left_frequency_hz,
        right_frequency_hz=payload.right_frequency_hz,
        pulse_frequency_hz=payload.pulse_frequency_hz,
        modulation_depth=payload.modulation_depth,
        layers=[layer.model_dump() for layer in payload.layers],
        preset_name=payload.preset_name,
        duration_seconds=payload.duration_seconds,
        sample_rate=payload.sample_rate,
        amplitude=payload.amplitude,
        fade_in_seconds=payload.fade_in_seconds,
        fade_out_seconds=payload.fade_out_seconds,
        seamless_loop=payload.seamless_loop,
        loop_crossfade_seconds=payload.loop_crossfade_seconds,
        seed=payload.seed,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_audio_job(db: Session, job_id: uuid.UUID) -> AudioJob | None:
    return db.get(AudioJob, job_id)


def list_audio_jobs(db: Session, limit: int = 50) -> list[AudioJob]:
    statement = (
        select(AudioJob)
        .order_by(AudioJob.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))
EOF

cat > apps/api/app/services/audio_generator.py <<'EOF'
import struct
import uuid
import wave
from pathlib import Path

from app.audio.dsp import (
    apply_fades,
    apply_loop_crossfade,
    generate_binaural_channels,
    generate_brown_noise,
    generate_isochronic_samples,
    generate_layered_tones,
    generate_pink_noise,
    generate_sine_samples,
    generate_white_noise,
)
from app.audio.presets import get_preset
from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse


def _mono_samples(request: AudioGenerationRequest) -> list[float]:
    if request.mode == AudioMode.SINE:
        return generate_sine_samples(
            request.frequency_hz or 432.0,
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
        )

    if request.mode == AudioMode.LAYERED_TONES:
        return generate_layered_tones(
            [(layer.frequency_hz, layer.amplitude) for layer in request.layers],
            request.duration_seconds,
            request.sample_rate,
        )

    if request.mode == AudioMode.WHITE_NOISE:
        return generate_white_noise(
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
            request.seed,
        )

    if request.mode == AudioMode.PINK_NOISE:
        return generate_pink_noise(
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
            request.seed,
        )

    if request.mode == AudioMode.BROWN_NOISE:
        return generate_brown_noise(
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
            request.seed,
        )

    if request.mode == AudioMode.ISOCHRONIC_TONES:
        return generate_isochronic_samples(
            carrier_frequency_hz=request.frequency_hz or 220.0,
            pulse_frequency_hz=request.pulse_frequency_hz or 10.0,
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
            modulation_depth=request.modulation_depth,
        )

    if request.mode == AudioMode.PRESET:
        preset = get_preset(request.preset_name or "")

        if preset.mode == "layered_tones":
            return generate_layered_tones(
                [(layer.frequency_hz, layer.amplitude) for layer in preset.layers],
                request.duration_seconds,
                request.sample_rate,
            )

        if preset.mode == "pink_noise":
            return generate_pink_noise(
                request.duration_seconds,
                request.sample_rate,
                preset.noise_amplitude,
                request.seed,
            )

        if preset.mode == "brown_noise":
            return generate_brown_noise(
                request.duration_seconds,
                request.sample_rate,
                preset.noise_amplitude,
                request.seed,
            )

    raise ValueError(f"Unsupported mono audio mode: {request.mode}")


def _process_channel(
    samples: list[float],
    request: AudioGenerationRequest,
) -> list[float]:
    samples = apply_fades(
        samples,
        request.sample_rate,
        request.fade_in_seconds,
        request.fade_out_seconds,
    )

    if request.seamless_loop:
        samples = apply_loop_crossfade(
            samples,
            request.sample_rate,
            request.loop_crossfade_seconds,
        )

    return samples


def _write_wav(
    output_path: Path,
    sample_rate: int,
    channels: list[list[float]],
) -> None:
    frame_count = len(channels[0])

    if any(len(channel) != frame_count for channel in channels):
        raise ValueError("All channels must have the same frame count")

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(len(channels))
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()

        for frame_index in range(frame_count):
            for channel in channels:
                sample = max(-1.0, min(1.0, channel[frame_index]))
                frames.extend(struct.pack("<h", int(sample * 32767)))

        wav_file.writeframes(bytes(frames))


def generate_audio(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_id = str(uuid.uuid4())
    output_path = output_dir / f"{asset_id}.wav"

    if request.mode == AudioMode.BINAURAL_BEATS:
        left, right = generate_binaural_channels(
            request.left_frequency_hz or 200.0,
            request.right_frequency_hz or 210.0,
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
        )
        channels = [
            _process_channel(left, request),
            _process_channel(right, request),
        ]
    else:
        mono = _process_channel(_mono_samples(request), request)

        if request.channels == ChannelMode.STEREO:
            channels = [mono[:], mono[:]]
        else:
            channels = [mono]

    _write_wav(output_path, request.sample_rate, channels)

    response_frequency = (
        request.frequency_hz
        if request.mode in {AudioMode.SINE, AudioMode.ISOCHRONIC_TONES}
        else None
    )

    return AudioGenerationResponse(
        id=asset_id,
        title=request.title,
        mode=request.mode.value,
        channels=request.channels.value,
        frequency_hz=response_frequency,
        duration_seconds=request.duration_seconds,
        sample_rate=request.sample_rate,
        status="generated",
        file_path=str(output_path),
    )


def generate_sine_wave(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    return generate_audio(request=request, output_dir=output_dir)
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/worker/app/main.py")
content = path.read_text(encoding="utf-8")

content = content.replace(
    "from app.audio.types import AudioMode  # noqa: E402",
    "from app.audio.types import AudioMode, ChannelMode  # noqa: E402",
)

old = """            mode=AudioMode(job.mode),
            frequency_hz=job.frequency_hz,
            layers=[
"""
new = """            mode=AudioMode(job.mode),
            channels=ChannelMode(job.channels),
            frequency_hz=job.frequency_hz,
            left_frequency_hz=job.left_frequency_hz,
            right_frequency_hz=job.right_frequency_hz,
            pulse_frequency_hz=job.pulse_frequency_hz,
            modulation_depth=job.modulation_depth,
            layers=[
"""

if old not in content:
    raise SystemExit("Expected worker request block was not found.")

content = content.replace(old, new)

old2 = """            fade_in_seconds=job.fade_in_seconds,
            fade_out_seconds=job.fade_out_seconds,
            seed=job.seed,
"""
new2 = """            fade_in_seconds=job.fade_in_seconds,
            fade_out_seconds=job.fade_out_seconds,
            seamless_loop=job.seamless_loop,
            loop_crossfade_seconds=job.loop_crossfade_seconds,
            seed=job.seed,
"""

if old2 not in content:
    raise SystemExit("Expected worker fade block was not found.")

path.write_text(content.replace(old2, new2), encoding="utf-8")
PY

cat > database/migrations/versions/0005_add_stereo_binaural_and_isochronic_fields.py <<'EOF'
"""add stereo binaural and isochronic fields

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audio_jobs",
        sa.Column("channels", sa.String(length=20), nullable=False, server_default="mono"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("left_frequency_hz", sa.Float(), nullable=True),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("right_frequency_hz", sa.Float(), nullable=True),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("pulse_frequency_hz", sa.Float(), nullable=True),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("modulation_depth", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("seamless_loop", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("loop_crossfade_seconds", sa.Float(), nullable=False, server_default="0.25"),
    )


def downgrade() -> None:
    op.drop_column("audio_jobs", "loop_crossfade_seconds")
    op.drop_column("audio_jobs", "seamless_loop")
    op.drop_column("audio_jobs", "modulation_depth")
    op.drop_column("audio_jobs", "pulse_frequency_hz")
    op.drop_column("audio_jobs", "right_frequency_hz")
    op.drop_column("audio_jobs", "left_frequency_hz")
    op.drop_column("audio_jobs", "channels")
EOF

cat > apps/api/tests/test_binaural_isochronic.py <<'EOF'
import wave
from pathlib import Path

import pytest

from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def test_binaural_requires_stereo() -> None:
    with pytest.raises(ValueError):
        AudioGenerationRequest(
            title="Invalid Binaural",
            mode=AudioMode.BINAURAL_BEATS,
            channels=ChannelMode.MONO,
            left_frequency_hz=200,
            right_frequency_hz=210,
            duration_seconds=1,
            sample_rate=8000,
        )


def test_generate_binaural_stereo(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Alpha Binaural",
        mode=AudioMode.BINAURAL_BEATS,
        channels=ChannelMode.STEREO,
        left_frequency_hz=200,
        right_frequency_hz=210,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 8000


def test_generate_isochronic_tone(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Alpha Isochronic",
        mode=AudioMode.ISOCHRONIC_TONES,
        channels=ChannelMode.MONO,
        frequency_hz=220,
        pulse_frequency_hz=10,
        modulation_depth=1.0,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    assert result.frequency_hz == 220

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getnframes() == 8000
EOF

cat > apps/api/tests/test_seamless_loop.py <<'EOF'
from app.audio.dsp import apply_loop_crossfade


def test_loop_crossfade_reduces_boundary_difference() -> None:
    samples = [1.0] * 100 + [-1.0] * 100
    original_difference = abs(samples[0] - samples[-1])

    result = apply_loop_crossfade(
        samples=samples,
        sample_rate=100,
        crossfade_seconds=0.2,
    )

    final_difference = abs(result[0] - result[-1])

    assert final_difference < original_difference
EOF

cat > docs/06-factories/audio/advanced-dsp.md <<'EOF'
# Advanced DSP Modes

## Binaural Beats

Binaural output requires stereo audio.

The left and right channels use separate carrier frequencies. The perceived beat frequency is their absolute difference.

Example:

- left: 200 Hz
- right: 210 Hz
- difference: 10 Hz

This feature is intended for ambient, meditation and relaxation content. It must not be presented as medical treatment.

## Isochronic Tones

Isochronic tones use amplitude modulation of a carrier tone.

Parameters:

- carrier frequency;
- pulse frequency;
- modulation depth;
- amplitude;
- duration.

## Stereo Output

Supported modes can be rendered as:

- mono;
- stereo duplicated channels;
- true stereo binaural channels.

## Seamless Looping

When enabled, the engine applies a boundary crossfade to reduce discontinuity between the end and beginning of the asset.

This first implementation reduces edge mismatch. Future versions should support phase-aware and content-aware loop construction.
EOF

echo "AION Update 010 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
