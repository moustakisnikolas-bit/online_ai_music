#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-016-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

for file in \
  "apps/api/app/main.py" \
  "apps/api/app/models/audio_job.py" \
  "apps/api/app/schemas/audio_job.py"; do
  if [[ -f "${file}" ]]; then
    mkdir -p "${BACKUP_DIR}/$(dirname "${file}")"
    cp "${file}" "${BACKUP_DIR}/${file}"
  fi
done

mkdir -p apps/api/app/api/routes
mkdir -p apps/api/app/services
mkdir -p apps/api/app/schemas
mkdir -p apps/api/tests
mkdir -p database/migrations/versions
mkdir -p docs/07-integrations
mkdir -p docs/03-requirements

cat > apps/api/app/services/metadata_generator.py <<'EOF'
from dataclasses import dataclass


SAFE_CONTEXT_LABELS = {
    "sleep": "Sleep",
    "relaxation": "Relaxation",
    "meditation": "Meditation",
    "focus": "Focus",
    "ambient": "Ambient",
}


@dataclass(frozen=True)
class MetadataPackage:
    title: str
    subtitle: str
    description: str
    keywords: list[str]
    category: str
    language: str
    compliance_note: str


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def generate_metadata_package(
    *,
    source_title: str,
    mode: str,
    duration_seconds: int,
    context: str = "ambient",
    language: str = "en",
    frequency_hz: float | None = None,
    texture_mode: str | None = None,
) -> MetadataPackage:
    clean_title = _clean_text(source_title)
    context_label = SAFE_CONTEXT_LABELS.get(context, "Ambient")
    duration_minutes = max(1, round(duration_seconds / 60))

    details: list[str] = []

    if frequency_hz is not None:
        details.append(f"{frequency_hz:g} Hz")

    if texture_mode and texture_mode != "none":
        details.append(texture_mode.replace("_", " ").title())

    details.append(mode.replace("_", " ").title())
    details_text = " · ".join(details)

    title = f"{clean_title} — {context_label} Audio"
    subtitle = f"{details_text} · {duration_minutes} Minutes"

    description = (
        f"{clean_title} is an original {context.lower()} audio soundscape "
        f"created with {mode.replace('_', ' ')} synthesis. "
        f"Duration: approximately {duration_minutes} minutes. "
        "Designed for background listening, relaxation, meditation, sleep "
        "or focus according to personal preference. "
        "This content does not provide medical treatment or guaranteed "
        "therapeutic effects."
    )

    keywords = [
        context.lower(),
        "ambient audio",
        "relaxation",
        "background sound",
        mode.replace("_", " "),
        "original audio",
    ]

    if frequency_hz is not None:
        keywords.append(f"{frequency_hz:g} hz")

    if texture_mode and texture_mode != "none":
        keywords.append(texture_mode.replace("_", " "))

    return MetadataPackage(
        title=title,
        subtitle=subtitle,
        description=description,
        keywords=sorted(set(keywords)),
        category=context_label,
        language=language,
        compliance_note=(
            "Use as ambient or relaxation content. Do not present this asset "
            "as medical treatment, disease prevention or guaranteed therapy."
        ),
    )
EOF

cat > apps/api/app/schemas/catalog.py <<'EOF'
import uuid

from pydantic import BaseModel, Field


class MetadataGenerateRequest(BaseModel):
    source_title: str = Field(min_length=1, max_length=255)
    mode: str = Field(min_length=1, max_length=50)
    duration_seconds: int = Field(gt=0)
    context: str = Field(default="ambient", max_length=50)
    language: str = Field(default="en", min_length=2, max_length=10)
    frequency_hz: float | None = Field(default=None, gt=0, le=20000)
    texture_mode: str | None = Field(default=None, max_length=50)


class MetadataPackageResponse(BaseModel):
    title: str
    subtitle: str
    description: str
    keywords: list[str]
    category: str
    language: str
    compliance_note: str


class ReviewDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class ReviewDecisionResponse(BaseModel):
    job_id: uuid.UUID
    review_status: str
    reason: str | None
EOF

cat > apps/api/app/api/routes/catalog.py <<'EOF'
from fastapi import APIRouter

from app.schemas.catalog import (
    MetadataGenerateRequest,
    MetadataPackageResponse,
)
from app.services.metadata_generator import generate_metadata_package

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.post(
    "/metadata/generate",
    response_model=MetadataPackageResponse,
)
def generate_metadata(
    payload: MetadataGenerateRequest,
) -> MetadataPackageResponse:
    package = generate_metadata_package(
        source_title=payload.source_title,
        mode=payload.mode,
        duration_seconds=payload.duration_seconds,
        context=payload.context,
        language=payload.language,
        frequency_hz=payload.frequency_hz,
        texture_mode=payload.texture_mode,
    )

    return MetadataPackageResponse(
        title=package.title,
        subtitle=package.subtitle,
        description=package.description,
        keywords=package.keywords,
        category=package.category,
        language=package.language,
        compliance_note=package.compliance_note,
    )
EOF

cat > apps/api/app/api/routes/review.py <<'EOF'
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.models.audio_job import AudioJob
from app.schemas.catalog import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)

router = APIRouter(prefix="/audio/jobs", tags=["review"])


def _get_job(db: Session, job_id: uuid.UUID) -> AudioJob:
    job = db.get(AudioJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio job not found.",
        )

    return job


@router.post(
    "/{job_id}/approve",
    response_model=ReviewDecisionResponse,
)
def approve_audio_job(
    job_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
) -> ReviewDecisionResponse:
    job = _get_job(db, job_id)

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed jobs can be approved.",
        )

    job.review_status = "approved"
    job.review_reason = payload.reason
    db.commit()

    return ReviewDecisionResponse(
        job_id=job.id,
        review_status=job.review_status,
        reason=job.review_reason,
    )


@router.post(
    "/{job_id}/reject",
    response_model=ReviewDecisionResponse,
)
def reject_audio_job(
    job_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
) -> ReviewDecisionResponse:
    job = _get_job(db, job_id)

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed jobs can be rejected.",
        )

    job.review_status = "rejected"
    job.review_reason = payload.reason
    db.commit()

    return ReviewDecisionResponse(
        job_id=job.id,
        review_status=job.review_status,
        reason=job.review_reason,
    )
EOF

python3 - <<'PY'
from pathlib import Path

model_path = Path("apps/api/app/models/audio_job.py")
content = model_path.read_text(encoding="utf-8")

needle = """    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued", index=True)
    output_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
"""
replacement = """    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued", index=True)
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
"""

if needle not in content:
    raise SystemExit("Expected AudioJob status block not found.")

model_path.write_text(
    content.replace(needle, replacement),
    encoding="utf-8",
)

schema_path = Path("apps/api/app/schemas/audio_job.py")
schema = schema_path.read_text(encoding="utf-8")

needle = """    status: str
    output_file_path: str | None
"""
replacement = """    status: str
    review_status: str
    review_reason: str | None
    output_file_path: str | None
"""

if needle not in schema:
    raise SystemExit("Expected AudioJobResponse status block not found.")

schema_path.write_text(
    schema.replace(needle, replacement),
    encoding="utf-8",
)
PY

cat > database/migrations/versions/0007_add_audio_review_workflow.py <<'EOF'
"""add audio review workflow

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audio_jobs",
        sa.Column(
            "review_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("review_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_audio_jobs_review_status",
        "audio_jobs",
        ["review_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audio_jobs_review_status",
        table_name="audio_jobs",
    )
    op.drop_column("audio_jobs", "review_reason")
    op.drop_column("audio_jobs", "review_status")
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/main.py")
content = path.read_text(encoding="utf-8")

imports = [
    "from app.api.routes.catalog import router as catalog_router\n",
    "from app.api.routes.review import router as review_router\n",
]

marker = "from app.api.routes.projects import router as projects_router\n"

for import_line in imports:
    if import_line not in content:
        if marker not in content:
            raise SystemExit("Expected project import marker not found.")
        content = content.replace(marker, marker + import_line)

routes = [
    'app.include_router(catalog_router, prefix="/api/v1")\n',
    'app.include_router(review_router, prefix="/api/v1")\n',
]

route_marker = 'app.include_router(projects_router, prefix="/api/v1")\n'

for route_line in routes:
    if route_line not in content:
        if route_marker not in content:
            raise SystemExit("Expected project route marker not found.")
        content = content.replace(route_marker, route_marker + route_line)

path.write_text(content, encoding="utf-8")
PY

cat > apps/api/tests/test_metadata_generator.py <<'EOF'
from app.services.metadata_generator import generate_metadata_package


def test_metadata_package_uses_safe_language() -> None:
    package = generate_metadata_package(
        source_title="Night Rain",
        mode="mixed_ambient",
        duration_seconds=3600,
        context="sleep",
        frequency_hz=432,
        texture_mode="rain",
    )

    assert "Night Rain" in package.title
    assert "432 hz" in package.keywords
    assert "rain" in package.keywords
    assert "medical treatment" in package.description
    assert "guaranteed" in package.compliance_note


def test_metadata_package_has_unique_keywords() -> None:
    package = generate_metadata_package(
        source_title="Brown Noise",
        mode="brown_noise",
        duration_seconds=600,
        context="ambient",
    )

    assert len(package.keywords) == len(set(package.keywords))
EOF

cat > apps/api/tests/test_catalog_api.py <<'EOF'
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_generate_catalog_metadata() -> None:
    response = client.post(
        "/api/v1/catalog/metadata/generate",
        json={
            "source_title": "Night Rain",
            "mode": "mixed_ambient",
            "duration_seconds": 600,
            "context": "sleep",
            "language": "en",
            "frequency_hz": 432,
            "texture_mode": "rain",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "Sleep"
    assert "Night Rain" in payload["title"]
    assert "medical treatment" in payload["description"]
EOF

cat > docs/03-requirements/mvp-004-review-and-metadata.md <<'EOF'
# MVP-004: Review and Metadata

## Objective

Ensure generated assets can be reviewed before future publishing and can receive a safe, platform-neutral metadata package.

## Review States

- pending
- approved
- rejected

## Rules

- Only completed jobs can be approved.
- Only completed jobs can be rejected.
- Publishing integrations must require `approved`.
- Review decisions may include a reason.
- Review actions must later be added to the audit log.

## Metadata Package

The generated package includes:

- title;
- subtitle;
- description;
- keywords;
- category;
- language;
- compliance note.

## Language Safety

Metadata must not claim:

- disease treatment;
- DNA repair;
- toxin removal;
- guaranteed neurological results;
- replacement of medical care.
EOF

cat > docs/07-integrations/publishing-package.md <<'EOF'
# Platform-Neutral Publishing Package

## Purpose

The current catalog metadata is platform-neutral.

It can later be transformed into:

- YouTube title and description;
- distributor release metadata;
- Apple Music metadata;
- Amazon Music metadata;
- website content;
- social media copy.

## Current Scope

No automatic publishing occurs.

The current implementation prepares metadata and requires human review.

## Future Publishing Gate

A publishing adapter must verify:

1. the audio job completed;
2. the asset exists;
3. metadata exists;
4. review status is approved;
5. platform credentials are available;
6. platform-specific validation passes.
EOF

echo "AION Update 016 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Remaining planned updates after this one: 4"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
