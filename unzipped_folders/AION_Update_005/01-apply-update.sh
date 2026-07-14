#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-$(pwd)}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

mkdir -p "${TARGET}/apps/api/app/api/routes"
mkdir -p "${TARGET}/apps/api/app/core"
mkdir -p "${TARGET}/apps/api/app/db"
mkdir -p "${TARGET}/apps/api/app/models"
mkdir -p "${TARGET}/apps/api/app/schemas"
mkdir -p "${TARGET}/apps/api/app/services"
mkdir -p "${TARGET}/apps/api/tests"
mkdir -p "${TARGET}/apps/worker/app"
mkdir -p "${TARGET}/apps/worker/tests"
mkdir -p "${TARGET}/database/migrations/versions"
mkdir -p "${TARGET}/data/generated/audio"
mkdir -p "${TARGET}/scripts/dev"

cat > "${TARGET}/pyproject.toml" <<'EOF'
[project]
name = "aion"
version = "0.1.0"
description = "AI Autonomous Content Operating System"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1.0",
  "uvicorn[standard]>=0.34,<1.0",
  "sqlalchemy>=2.0,<3.0",
  "psycopg[binary]>=3.2,<4.0",
  "alembic>=1.14,<2.0",
  "pydantic>=2.10,<3.0",
  "pydantic-settings>=2.7,<3.0",
  "redis>=5.2,<6.0",
  "minio>=7.2,<8.0",
  "httpx>=0.28,<1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3,<9.0",
  "pytest-asyncio>=0.25,<1.0",
  "ruff>=0.9,<1.0",
  "mypy>=1.14,<2.0",
]

[tool.pytest.ini_options]
pythonpath = ["apps/api", "apps/worker"]
testpaths = ["apps/api/tests", "apps/worker/tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
EOF

cat > "${TARGET}/apps/api/app/core/config.py" <<'EOF'
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AION API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "postgresql+psycopg://aion:aion@postgres:5432/aion"
    redis_url: str = "redis://redis:6379/0"
    generated_audio_dir: str = "data/generated/audio"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def audio_output_path(self) -> Path:
        return Path(self.generated_audio_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
EOF

cat > "${TARGET}/apps/api/app/db/base.py" <<'EOF'
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
EOF

cat > "${TARGET}/apps/api/app/db/session.py" <<'EOF'
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
EOF

cat > "${TARGET}/apps/api/app/models/project.py" <<'EOF'
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
EOF

cat > "${TARGET}/apps/api/app/models/audio_asset.py" <<'EOF'
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AudioAsset(Base):
    __tablename__ = "audio_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    waveform: Mapped[str] = mapped_column(String(50), nullable=False, default="sine")
    frequency_hz: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=44100)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="generated")
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
EOF

cat > "${TARGET}/apps/api/app/models/__init__.py" <<'EOF'
from app.models.audio_asset import AudioAsset
from app.models.project import Project

__all__ = ["AudioAsset", "Project"]
EOF

cat > "${TARGET}/apps/api/app/schemas/audio.py" <<'EOF'
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
EOF

cat > "${TARGET}/apps/api/app/services/audio_generator.py" <<'EOF'
import math
import struct
import uuid
import wave
from pathlib import Path

from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse


def generate_sine_wave(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    output_dir.mkdir(parents=True, exist_ok=True)

    asset_id = str(uuid.uuid4())
    output_path = output_dir / f"{asset_id}.wav"
    frame_count = request.duration_seconds * request.sample_rate

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(request.sample_rate)

        for frame_index in range(frame_count):
            time_position = frame_index / request.sample_rate
            sample_value = request.amplitude * math.sin(
                2.0 * math.pi * request.frequency_hz * time_position
            )
            pcm_value = int(max(-1.0, min(1.0, sample_value)) * 32767)
            wav_file.writeframesraw(struct.pack("<h", pcm_value))

    return AudioGenerationResponse(
        id=asset_id,
        title=request.title,
        frequency_hz=request.frequency_hz,
        duration_seconds=request.duration_seconds,
        sample_rate=request.sample_rate,
        status="generated",
        file_path=str(output_path),
    )
EOF

cat > "${TARGET}/apps/api/app/api/routes/health.py" <<'EOF'
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
EOF

cat > "${TARGET}/apps/api/app/api/routes/audio.py" <<'EOF'
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse
from app.services.audio_generator import generate_sine_wave

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/generate", response_model=AudioGenerationResponse)
def generate_audio(request: AudioGenerationRequest) -> AudioGenerationResponse:
    settings = get_settings()

    try:
        return generate_sine_wave(
            request=request,
            output_dir=settings.audio_output_path,
        )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Audio generation failed: {exc}",
        ) from exc
EOF

cat > "${TARGET}/apps/api/app/main.py" <<'EOF'
from fastapi import FastAPI

from app.api.routes.audio import router as audio_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AION core API",
)

app.include_router(health_router)
app.include_router(audio_router, prefix="/api/v1")
EOF

for file in \
  "${TARGET}/apps/api/app/__init__.py" \
  "${TARGET}/apps/api/app/api/__init__.py" \
  "${TARGET}/apps/api/app/api/routes/__init__.py" \
  "${TARGET}/apps/api/app/core/__init__.py" \
  "${TARGET}/apps/api/app/db/__init__.py" \
  "${TARGET}/apps/api/app/schemas/__init__.py" \
  "${TARGET}/apps/api/app/services/__init__.py"; do
  : > "${file}"
done

cat > "${TARGET}/apps/api/tests/test_health.py" <<'EOF'
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
EOF

cat > "${TARGET}/apps/api/tests/test_audio_generation.py" <<'EOF'
import wave
from pathlib import Path

from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_sine_wave


def test_generate_sine_wave(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Test Tone",
        frequency_hz=432,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
    )

    result = generate_sine_wave(
        request=request,
        output_dir=tmp_path,
    )

    output_path = Path(result.file_path)

    assert output_path.exists()
    assert result.frequency_hz == 432
    assert result.duration_seconds == 1

    with wave.open(str(output_path), "r") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 8000
EOF

cat > "${TARGET}/apps/worker/app/main.py" <<'EOF'
import os
import time


def run_worker() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    print(f"AION worker started. Redis: {redis_url}", flush=True)

    while True:
        time.sleep(30)
        print("AION worker heartbeat", flush=True)


if __name__ == "__main__":
    run_worker()
EOF

: > "${TARGET}/apps/worker/app/__init__.py"

cat > "${TARGET}/apps/api/Dockerfile" <<'EOF'
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .

COPY apps/api /app/apps/api
COPY data /app/data

ENV PYTHONPATH=/app/apps/api

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

cat > "${TARGET}/apps/worker/Dockerfile" <<'EOF'
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .

COPY apps/worker /app/apps/worker

ENV PYTHONPATH=/app/apps/worker

CMD ["python", "-m", "app.main"]
EOF

cat > "${TARGET}/alembic.ini" <<'EOF'
[alembic]
script_location = database/migrations
prepend_sys_path = apps/api
sqlalchemy.url = postgresql+psycopg://aion:aion@localhost:5432/aion

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
EOF

cat > "${TARGET}/database/migrations/env.py" <<'EOF'
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.base import Base
from app.models import AudioAsset, Project  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
EOF

cat > "${TARGET}/database/migrations/script.py.mako" <<'EOF'
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
EOF

cat > "${TARGET}/database/migrations/versions/0001_create_projects_and_audio_assets.py" <<'EOF'
"""create projects and audio assets

Revision ID: 0001
Revises:
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)

    op.create_table(
        "audio_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("waveform", sa.String(length=50), nullable=False),
        sa.Column("frequency_hz", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audio_assets")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_table("projects")
EOF

cat > "${TARGET}/docker-compose.yml" <<'EOF'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: aion
      POSTGRES_PASSWORD: aion
      POSTGRES_DB: aion
    ports:
      - "5432:5432"
    volumes:
      - aion-postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aion -d aion"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: aion
      MINIO_ROOT_PASSWORD: change-me-now
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - aion-minio:/data

  api:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    environment:
      APP_ENV: development
      DATABASE_URL: postgresql+psycopg://aion:aion@postgres:5432/aion
      REDIS_URL: redis://redis:6379/0
      GENERATED_AUDIO_DIR: /app/data/generated/audio
    ports:
      - "8000:8000"
    volumes:
      - ./data/generated:/app/data/generated
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started

  worker:
    build:
      context: .
      dockerfile: apps/worker/Dockerfile
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on:
      redis:
        condition: service_started

volumes:
  aion-postgres:
  aion-minio:
EOF

cat > "${TARGET}/.env.example" <<'EOF'
APP_NAME=AION API
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
DATABASE_URL=postgresql+psycopg://aion:aion@localhost:5432/aion
REDIS_URL=redis://localhost:6379/0
GENERATED_AUDIO_DIR=data/generated/audio
MINIO_ROOT_USER=aion
MINIO_ROOT_PASSWORD=change-me-now
EOF

cat > "${TARGET}/Makefile" <<'EOF'
.PHONY: help install test lint api infra-up infra-down migrate doctor

help:
	@echo "AION commands"
	@echo "  make install"
	@echo "  make test"
	@echo "  make lint"
	@echo "  make api"
	@echo "  make infra-up"
	@echo "  make infra-down"
	@echo "  make migrate"
	@echo "  make doctor"

install:
	python3.12 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

test:
	PYTHONPATH=apps/api:apps/worker .venv/bin/pytest

lint:
	.venv/bin/ruff check apps

api:
	PYTHONPATH=apps/api .venv/bin/uvicorn app.main:app --reload

infra-up:
	docker compose up -d --build

infra-down:
	docker compose down

migrate:
	PYTHONPATH=apps/api .venv/bin/alembic upgrade head

doctor:
	./tools/aion/aion doctor
	python3 --version
	docker --version
	docker compose version
EOF

cat > "${TARGET}/scripts/dev/bootstrap-local.sh" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python3}"

"${PYTHON_BIN}" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"

echo "Local Python environment is ready."
echo "Run: make test"
echo "Run: make api"
EOF
chmod +x "${TARGET}/scripts/dev/bootstrap-local.sh"

cat > "${TARGET}/docs/03-requirements/mvp-001-core-audio.md" <<'EOF'
# MVP-001: Core Audio Generation

## Objective

Provide the first functional AION capability: generate a valid WAV file through an API request.

## Scope

- FastAPI service
- Health endpoint
- Audio generation endpoint
- Configurable frequency
- Configurable duration
- Configurable sample rate
- Local output storage
- Automated tests

## Non-Goals

- Music composition
- Ambient layering
- AI provider integration
- Publishing
- Monetization
- Medical or therapeutic claims

## Acceptance Criteria

1. `GET /health` returns HTTP 200.
2. `POST /api/v1/audio/generate` creates a valid mono WAV file.
3. Invalid frequencies or durations return validation errors.
4. Unit tests pass.
5. The service can run locally or through Docker Compose.
EOF

cat > "${TARGET}/docs/04-architecture/mvp-application-architecture.md" <<'EOF'
# MVP Application Architecture

## Runtime Components

- FastAPI API
- PostgreSQL
- Redis
- MinIO
- Background worker

## Initial Data Flow

1. Client submits an audio generation request.
2. API validates the request.
3. Generator creates a WAV asset.
4. Asset is written to local generated storage.
5. API returns asset metadata.

## Current Limitations

- Synchronous generation
- Local file output
- No database persistence in the endpoint yet
- No queue-backed jobs yet
- No authentication yet

These limitations are intentional for the first working vertical slice.
EOF

echo "Update 005 applied successfully."
echo
echo "Next commands:"
echo "  cd \"${TARGET}\""
echo "  ./scripts/dev/bootstrap-local.sh"
echo "  make test"
echo "  make api"
