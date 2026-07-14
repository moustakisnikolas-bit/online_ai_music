#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-008-$(date +%Y%m%d-%H%M%S)"
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
  "${TARGET}/apps/api/app/schemas/audio.py" \
  "${TARGET}/apps/api/app/schemas/audio_job.py" \
  "${TARGET}/apps/api/app/models/audio_job.py" \
  "${TARGET}/apps/api/app/services/audio_generator.py" \
  "${TARGET}/apps/worker/app/main.py"; do
  backup_file "${file}"
done

mkdir -p apps/api/app/audio
mkdir -p apps/api/app/services
mkdir -p apps/api/tests
mkdir -p docs/06-factories/audio
mkdir -p database/migrations/versions

cat > apps/api/app/audio/types.py <<'EOF'
from enum import StrEnum


class AudioMode(StrEnum):
    SINE = "sine"
    LAYERED_TONES = "layered_tones"
    WHITE_NOISE = "white_noise"
    PINK_NOISE = "pink_noise"
    BROWN_NOISE = "brown_noise"
    PRESET = "preset"
EOF

cat > apps/api/app/audio/presets.py <<'EOF'
from dataclasses import dataclass


@dataclass(frozen=True)
class ToneLayer:
    frequency_hz: float
    amplitude: float


@dataclass(frozen=True)
class AudioPreset:
    name: str
    mode: str
    layers: tuple[ToneLayer, ...] = ()
    noise_amplitude: float = 0.0


PRESETS: dict[str, AudioPreset] = {
    "calm-432": AudioPreset(
        name="calm-432",
        mode="layered_tones",
        layers=(
            ToneLayer(frequency_hz=432.0, amplitude=0.16),
            ToneLayer(frequency_hz=216.0, amplitude=0.08),
        ),
    ),
    "focus-alpha-bed": AudioPreset(
        name="focus-alpha-bed",
        mode="layered_tones",
        layers=(
            ToneLayer(frequency_hz=220.0, amplitude=0.12),
            ToneLayer(frequency_hz=230.0, amplitude=0.12),
        ),
    ),
    "deep-brown": AudioPreset(
        name="deep-brown",
        mode="brown_noise",
        noise_amplitude=0.22,
    ),
    "soft-pink": AudioPreset(
        name="soft-pink",
        mode="pink_noise",
        noise_amplitude=0.18,
    ),
}


def get_preset(name: str) -> AudioPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown audio preset: {name}") from exc
EOF

cat > apps/api/app/audio/dsp.py <<'EOF'
import math
import random
from collections.abc import Iterable


def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


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
            gain = index / fade_in_frames
            result[index] *= gain

    if fade_out_frames > 0:
        start = total - fade_out_frames
        for index in range(fade_out_frames):
            gain = 1.0 - (index / fade_out_frames)
            result[start + index] *= gain

    return result


def normalize(samples: Iterable[float], peak: float = 0.95) -> list[float]:
    values = list(samples)
    maximum = max((abs(value) for value in values), default=0.0)

    if maximum == 0:
        return values

    scale = peak / maximum
    return [clamp(value * scale) for value in values]


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


def generate_white_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> list[float]:
    generator = random.Random(seed)
    frame_count = duration_seconds * sample_rate

    return [
        generator.uniform(-amplitude, amplitude)
        for _ in range(frame_count)
    ]


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

: > apps/api/app/audio/__init__.py

cat > apps/api/app/schemas/audio.py <<'EOF'
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
    fade_in_seconds: float = Field(default=1.0, ge=0, le=60)
    fade_out_seconds: float = Field(default=1.0, ge=0, le=60)
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
    fade_in_seconds: float = Field(default=1.0, ge=0, le=60)
    fade_out_seconds: float = Field(default=1.0, ge=0, le=60)
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
EOF

cat > apps/api/app/models/audio_job.py <<'EOF'
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
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
    frequency_hz: Mapped[float | None] = mapped_column(Float, nullable=True)
    layers: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    preset_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=44100)
    amplitude: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    fade_in_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    fade_out_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
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
        frequency_hz=payload.frequency_hz,
        layers=[layer.model_dump() for layer in payload.layers],
        preset_name=payload.preset_name,
        duration_seconds=payload.duration_seconds,
        sample_rate=payload.sample_rate,
        amplitude=payload.amplitude,
        fade_in_seconds=payload.fade_in_seconds,
        fade_out_seconds=payload.fade_out_seconds,
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
    generate_brown_noise,
    generate_layered_tones,
    generate_pink_noise,
    generate_sine_samples,
    generate_white_noise,
)
from app.audio.presets import get_preset
from app.audio.types import AudioMode
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse


def _samples_for_request(request: AudioGenerationRequest) -> list[float]:
    if request.mode == AudioMode.SINE:
        return generate_sine_samples(
            frequency_hz=request.frequency_hz or 432.0,
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
        )

    if request.mode == AudioMode.LAYERED_TONES:
        return generate_layered_tones(
            layers=[
                (layer.frequency_hz, layer.amplitude)
                for layer in request.layers
            ],
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
        )

    if request.mode == AudioMode.WHITE_NOISE:
        return generate_white_noise(
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
            seed=request.seed,
        )

    if request.mode == AudioMode.PINK_NOISE:
        return generate_pink_noise(
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
            seed=request.seed,
        )

    if request.mode == AudioMode.BROWN_NOISE:
        return generate_brown_noise(
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
            seed=request.seed,
        )

    if request.mode == AudioMode.PRESET:
        preset = get_preset(request.preset_name or "")

        if preset.mode == "layered_tones":
            return generate_layered_tones(
                layers=[
                    (layer.frequency_hz, layer.amplitude)
                    for layer in preset.layers
                ],
                duration_seconds=request.duration_seconds,
                sample_rate=request.sample_rate,
            )

        if preset.mode == "pink_noise":
            return generate_pink_noise(
                duration_seconds=request.duration_seconds,
                sample_rate=request.sample_rate,
                amplitude=preset.noise_amplitude,
                seed=request.seed,
            )

        if preset.mode == "brown_noise":
            return generate_brown_noise(
                duration_seconds=request.duration_seconds,
                sample_rate=request.sample_rate,
                amplitude=preset.noise_amplitude,
                seed=request.seed,
            )

        raise ValueError(f"Unsupported preset mode: {preset.mode}")

    raise ValueError(f"Unsupported audio mode: {request.mode}")


def generate_audio(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    output_dir.mkdir(parents=True, exist_ok=True)

    asset_id = str(uuid.uuid4())
    output_path = output_dir / f"{asset_id}.wav"

    samples = _samples_for_request(request)
    samples = apply_fades(
        samples=samples,
        sample_rate=request.sample_rate,
        fade_in_seconds=request.fade_in_seconds,
        fade_out_seconds=request.fade_out_seconds,
    )

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(request.sample_rate)

        frames = bytearray()
        for sample in samples:
            pcm_value = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(struct.pack("<h", pcm_value))

        wav_file.writeframes(bytes(frames))

    return AudioGenerationResponse(
        id=asset_id,
        title=request.title,
        mode=request.mode.value,
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

cat > apps/api/app/api/routes/audio.py <<'EOF'
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse
from app.services.audio_generator import generate_audio

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/generate", response_model=AudioGenerationResponse)
def generate_audio_endpoint(
    request: AudioGenerationRequest,
) -> AudioGenerationResponse:
    settings = get_settings()

    try:
        return generate_audio(
            request=request,
            output_dir=settings.audio_output_path,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Audio generation failed: {exc}",
        ) from exc
EOF

cat > apps/worker/app/main.py <<'EOF'
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from redis import Redis
from sqlalchemy.orm import Session

API_PATH = Path(__file__).resolve().parents[2] / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from app.audio.types import AudioMode  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.audio_job import AudioJob  # noqa: E402
from app.schemas.audio import AudioGenerationRequest, ToneLayerRequest  # noqa: E402
from app.services.audio_generator import generate_audio  # noqa: E402
from app.services.audio_queue import QUEUE_NAME  # noqa: E402


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def process_job(db: Session, job_id: uuid.UUID) -> None:
    settings = get_settings()
    job = db.get(AudioJob, job_id)

    if job is None:
        print(f"Audio job not found: {job_id}", flush=True)
        return

    if job.status not in {"queued", "retry"}:
        print(f"Skipping job {job_id} with status {job.status}", flush=True)
        return

    job.status = "processing"
    job.started_at = utc_now()
    job.error_message = None
    db.commit()

    try:
        request = AudioGenerationRequest(
            title=job.title,
            mode=AudioMode(job.mode),
            frequency_hz=job.frequency_hz,
            layers=[
                ToneLayerRequest(**layer)
                for layer in (job.layers or [])
            ],
            preset_name=job.preset_name,
            duration_seconds=job.duration_seconds,
            sample_rate=job.sample_rate,
            amplitude=job.amplitude,
            fade_in_seconds=job.fade_in_seconds,
            fade_out_seconds=job.fade_out_seconds,
            seed=job.seed,
        )

        result = generate_audio(
            request=request,
            output_dir=settings.audio_output_path,
        )

        job.status = "completed"
        job.output_file_path = result.file_path
        job.completed_at = utc_now()
        db.commit()
        print(f"Completed audio job: {job_id}", flush=True)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = utc_now()
        db.commit()
        print(f"Failed audio job {job_id}: {exc}", flush=True)


def run_worker() -> None:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)

    print(
        f"AION audio worker started. Queue: {QUEUE_NAME}. Redis: {settings.redis_url}",
        flush=True,
    )

    while True:
        item = client.brpop(QUEUE_NAME, timeout=10)

        if item is None:
            continue

        _, raw_message = item

        try:
            message = json.loads(raw_message)
            job_id = uuid.UUID(message["job_id"])
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"Invalid queue message: {raw_message}. Error: {exc}", flush=True)
            continue

        db = SessionLocal()
        try:
            process_job(db, job_id)
        finally:
            db.close()


if __name__ == "__main__":
    run_worker()
EOF

cat > database/migrations/versions/0003_expand_audio_jobs_for_ambient_modes.py <<'EOF'
"""expand audio jobs for ambient modes

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audio_jobs",
        sa.Column("mode", sa.String(length=50), nullable=False, server_default="sine"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("layers", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("preset_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("fade_in_seconds", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("fade_out_seconds", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("seed", sa.Integer(), nullable=True),
    )
    op.alter_column("audio_jobs", "frequency_hz", nullable=True)


def downgrade() -> None:
    op.alter_column("audio_jobs", "frequency_hz", nullable=False)
    op.drop_column("audio_jobs", "seed")
    op.drop_column("audio_jobs", "fade_out_seconds")
    op.drop_column("audio_jobs", "fade_in_seconds")
    op.drop_column("audio_jobs", "preset_name")
    op.drop_column("audio_jobs", "layers")
    op.drop_column("audio_jobs", "mode")
EOF

cat > apps/api/tests/test_ambient_audio.py <<'EOF'
import wave
from pathlib import Path

from app.audio.types import AudioMode
from app.schemas.audio import AudioGenerationRequest, ToneLayerRequest
from app.services.audio_generator import generate_audio


def assert_wav(path: Path, sample_rate: int, frames: int) -> None:
    assert path.exists()

    with wave.open(str(path), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == sample_rate
        assert wav_file.getnframes() == frames


def test_generate_white_noise(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="White Noise",
        mode=AudioMode.WHITE_NOISE,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=42,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "white_noise"
    assert_wav(Path(result.file_path), 8000, 8000)


def test_generate_layered_tones(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Layered Calm",
        mode=AudioMode.LAYERED_TONES,
        layers=[
            ToneLayerRequest(frequency_hz=432, amplitude=0.1),
            ToneLayerRequest(frequency_hz=216, amplitude=0.05),
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.2,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "layered_tones"
    assert_wav(Path(result.file_path), 8000, 8000)


def test_generate_preset(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Deep Brown",
        mode=AudioMode.PRESET,
        preset_name="deep-brown",
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.2,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=123,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "preset"
    assert_wav(Path(result.file_path), 8000, 8000)
EOF

cat > docs/06-factories/audio/ambient-audio-engine.md <<'EOF'
# Ambient Audio Engine

## Supported Modes

- sine
- layered_tones
- white_noise
- pink_noise
- brown_noise
- preset

## Initial Presets

- calm-432
- focus-alpha-bed
- deep-brown
- soft-pink

## Generation Controls

- duration
- sample rate
- amplitude
- frequency
- tone layers
- deterministic seed
- fade-in
- fade-out

## Safety and Product Language

Frequency-based content must be described as ambient, relaxation, meditation, sleep or focus content.

The product must not claim that a frequency:

- cures disease;
- repairs DNA;
- removes toxins;
- replaces medical care;
- guarantees neurological outcomes.

## Technical Limits

- Maximum duration through the API: 3600 seconds
- Maximum tone layers: 16
- Maximum frequency: 20 kHz
- Maximum amplitude: 1.0
- Mono 16-bit PCM WAV output in the current version

## Future Work

- Stereo rendering
- Binaural channel separation
- Isochronic modulation
- Nature-sound layering
- Seamless loops
- Streaming generation
- Chunked long-form rendering
- FLAC and MP3 encoding
EOF

echo "Update 008 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
