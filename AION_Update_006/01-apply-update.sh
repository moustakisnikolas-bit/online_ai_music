#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-$(pwd)}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

BACKUP_DIR="${TARGET}/.aion/backups/update-006-$(date +%Y%m%d-%H%M%S)"
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
  "${TARGET}/apps/api/app/models/__init__.py" \
  "${TARGET}/apps/api/app/api/routes/audio.py" \
  "${TARGET}/apps/api/app/main.py" \
  "${TARGET}/apps/worker/app/main.py" \
  "${TARGET}/apps/worker/Dockerfile" \
  "${TARGET}/docker-compose.yml" \
  "${TARGET}/Makefile"; do
  backup_file "${file}"
done

mkdir -p "${TARGET}/apps/api/app/api/dependencies"
mkdir -p "${TARGET}/apps/api/app/repositories"
mkdir -p "${TARGET}/apps/api/app/services"
mkdir -p "${TARGET}/apps/api/app/models"
mkdir -p "${TARGET}/apps/api/app/schemas"
mkdir -p "${TARGET}/apps/worker/app"
mkdir -p "${TARGET}/database/migrations/versions"

cat > "${TARGET}/apps/api/app/models/audio_job.py" <<'EOF'
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
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
    frequency_hz: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=44100)
    amplitude: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
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

cat > "${TARGET}/apps/api/app/models/__init__.py" <<'EOF'
from app.models.audio_asset import AudioAsset
from app.models.audio_job import AudioJob
from app.models.project import Project

__all__ = ["AudioAsset", "AudioJob", "Project"]
EOF

cat > "${TARGET}/apps/api/app/api/dependencies/database.py" <<'EOF'
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
EOF

: > "${TARGET}/apps/api/app/api/dependencies/__init__.py"

cat > "${TARGET}/apps/api/app/schemas/project.py" <<'EOF'
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.strip().split())


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_at: datetime
EOF

cat > "${TARGET}/apps/api/app/schemas/audio_job.py" <<'EOF'
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AudioJobCreate(BaseModel):
    project_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    frequency_hz: float = Field(gt=0, le=20000)
    duration_seconds: int = Field(gt=0, le=3600)
    sample_rate: int = Field(default=44100, ge=8000, le=192000)
    amplitude: float = Field(default=0.2, gt=0, le=1.0)


class AudioJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    frequency_hz: float
    duration_seconds: int
    sample_rate: int
    amplitude: float
    status: str
    output_file_path: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
EOF

cat > "${TARGET}/apps/api/app/repositories/audio_jobs.py" <<'EOF'
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audio_job import AudioJob
from app.schemas.audio_job import AudioJobCreate


def create_audio_job(db: Session, payload: AudioJobCreate) -> AudioJob:
    job = AudioJob(
        project_id=payload.project_id,
        title=payload.title,
        frequency_hz=payload.frequency_hz,
        duration_seconds=payload.duration_seconds,
        sample_rate=payload.sample_rate,
        amplitude=payload.amplitude,
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

cat > "${TARGET}/apps/api/app/repositories/projects.py" <<'EOF'
from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate


def create_project(db: Session, payload: ProjectCreate) -> Project:
    project = Project(
        name=payload.name,
        slug=payload.slug,
        status="draft",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
EOF

cat > "${TARGET}/apps/api/app/services/audio_queue.py" <<'EOF'
import json
import uuid

from redis import Redis

from app.core.config import get_settings

QUEUE_NAME = "aion:audio:jobs"


def build_job_message(job_id: uuid.UUID) -> str:
    return json.dumps(
        {
            "job_id": str(job_id),
            "type": "generate_sine_wave",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def enqueue_audio_job(job_id: uuid.UUID) -> None:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    client.lpush(QUEUE_NAME, build_job_message(job_id))
EOF

cat > "${TARGET}/apps/api/app/api/routes/projects.py" <<'EOF'
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.repositories.projects import create_project
from app.schemas.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        return create_project(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A project with this slug already exists.",
        ) from exc
EOF

cat > "${TARGET}/apps/api/app/api/routes/audio_jobs.py" <<'EOF'
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.repositories.audio_jobs import create_audio_job, get_audio_job, list_audio_jobs
from app.schemas.audio_job import AudioJobCreate, AudioJobResponse
from app.services.audio_queue import enqueue_audio_job

router = APIRouter(prefix="/audio/jobs", tags=["audio-jobs"])


@router.post("", response_model=AudioJobResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_audio_job(
    payload: AudioJobCreate,
    db: Session = Depends(get_db),
) -> AudioJobResponse:
    job = create_audio_job(db, payload)

    try:
        enqueue_audio_job(job.id)
    except Exception as exc:
        job.status = "queue_failed"
        job.error_message = str(exc)
        db.commit()
        db.refresh(job)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The audio job could not be queued.",
        ) from exc

    return job


@router.get("/{job_id}", response_model=AudioJobResponse)
def get_audio_job_endpoint(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AudioJobResponse:
    job = get_audio_job(db, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio job not found.",
        )

    return job


@router.get("", response_model=list[AudioJobResponse])
def list_audio_jobs_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AudioJobResponse]:
    return list_audio_jobs(db, limit=limit)
EOF

cat > "${TARGET}/apps/api/app/main.py" <<'EOF'
from fastapi import FastAPI

from app.api.routes.audio import router as audio_router
from app.api.routes.audio_jobs import router as audio_jobs_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="AION core API",
)

app.include_router(health_router)
app.include_router(audio_router, prefix="/api/v1")
app.include_router(audio_jobs_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
EOF

cat > "${TARGET}/apps/worker/app/main.py" <<'EOF'
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from redis import Redis
from sqlalchemy.orm import Session

API_PATH = Path(__file__).resolve().parents[2] / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.audio_job import AudioJob  # noqa: E402
from app.schemas.audio import AudioGenerationRequest  # noqa: E402
from app.services.audio_generator import generate_sine_wave  # noqa: E402
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
        result = generate_sine_wave(
            request=AudioGenerationRequest(
                title=job.title,
                frequency_hz=job.frequency_hz,
                duration_seconds=job.duration_seconds,
                sample_rate=job.sample_rate,
                amplitude=job.amplitude,
            ),
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

cat > "${TARGET}/apps/worker/Dockerfile" <<'EOF'
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .

COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker
COPY data /app/data

ENV PYTHONPATH=/app/apps/api:/app/apps/worker

CMD ["python", "/app/apps/worker/app/main.py"]
EOF

cat > "${TARGET}/database/migrations/versions/0002_create_audio_jobs.py" <<'EOF'
"""create audio jobs

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audio_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("frequency_hz", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("amplitude", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("output_file_path", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audio_jobs_project_id", "audio_jobs", ["project_id"])
    op.create_index("ix_audio_jobs_status", "audio_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_audio_jobs_status", table_name="audio_jobs")
    op.drop_index("ix_audio_jobs_project_id", table_name="audio_jobs")
    op.drop_table("audio_jobs")
EOF

cat > "${TARGET}/apps/api/tests/test_audio_queue.py" <<'EOF'
import json
import uuid

from app.services.audio_queue import build_job_message


def test_build_job_message() -> None:
    job_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

    message = json.loads(build_job_message(job_id))

    assert message == {
        "job_id": str(job_id),
        "type": "generate_sine_wave",
        "version": 1,
    }
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
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10

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

  migrate:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    command: ["alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: postgresql+psycopg://aion:aion@postgres:5432/aion
    depends_on:
      postgres:
        condition: service_healthy

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
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy

  worker:
    build:
      context: .
      dockerfile: apps/worker/Dockerfile
    environment:
      DATABASE_URL: postgresql+psycopg://aion:aion@postgres:5432/aion
      REDIS_URL: redis://redis:6379/0
      GENERATED_AUDIO_DIR: /app/data/generated/audio
    volumes:
      - ./data/generated:/app/data/generated
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy

volumes:
  aion-postgres:
  aion-minio:
EOF

cat > "${TARGET}/Makefile" <<'EOF'
.PHONY: help install test lint api worker infra-up infra-down migrate doctor

help:
	@echo "AION commands"
	@echo "  make install"
	@echo "  make test"
	@echo "  make lint"
	@echo "  make api"
	@echo "  make worker"
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

worker:
	PYTHONPATH=apps/api:apps/worker .venv/bin/python apps/worker/app/main.py

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

cat > "${TARGET}/docs/03-requirements/mvp-002-persistent-audio-jobs.md" <<'EOF'
# MVP-002: Persistent Audio Jobs

## Objective

Move audio generation from a synchronous request into a persistent queue-backed workflow.

## Functional Requirements

- Create projects.
- Submit audio jobs.
- Persist job state in PostgreSQL.
- Queue work in Redis.
- Process jobs in a worker.
- Retrieve job status.
- List recent jobs.
- Store output file paths.
- Preserve errors for diagnosis.

## Job States

- queued
- queue_failed
- processing
- completed
- failed

## Acceptance Criteria

1. An audio job receives a persistent UUID.
2. The API returns HTTP 202 for accepted jobs.
3. The worker updates the job to processing.
4. Successful completion stores an output path.
5. Failures store an error message.
6. Duplicate worker pickup does not process terminal jobs again.
EOF

echo "Update 006 applied successfully."
echo
echo "Backup created at:"
echo "  ${BACKUP_DIR}"
echo
echo "Next:"
echo "  cd \"${TARGET}\""
echo "  make test"
echo "  docker compose up -d --build"
echo "  open http://127.0.0.1:8000/docs"
