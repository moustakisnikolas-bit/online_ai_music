#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

python3 - <<'PY'
from pathlib import Path

replacements = {
    Path("apps/api/app/schemas/audio.py"): [
        (
            "fade_in_seconds: float = Field(default=1.0, ge=0, le=60)",
            "fade_in_seconds: float = Field(default=0.1, ge=0, le=60)",
        ),
        (
            "fade_out_seconds: float = Field(default=1.0, ge=0, le=60)",
            "fade_out_seconds: float = Field(default=0.1, ge=0, le=60)",
        ),
    ],
    Path("apps/api/app/schemas/audio_job.py"): [
        (
            "fade_in_seconds: float = Field(default=1.0, ge=0, le=60)",
            "fade_in_seconds: float = Field(default=0.1, ge=0, le=60)",
        ),
        (
            "fade_out_seconds: float = Field(default=1.0, ge=0, le=60)",
            "fade_out_seconds: float = Field(default=0.1, ge=0, le=60)",
        ),
    ],
    Path("apps/api/app/models/audio_job.py"): [
        (
            'fade_in_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)',
            'fade_in_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)',
        ),
        (
            'fade_out_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)',
            'fade_out_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)',
        ),
    ],
}

for path, pairs in replacements.items():
    if not path.exists():
        raise SystemExit(f"Missing expected file: {path}")

    content = path.read_text(encoding="utf-8")

    for old, new in pairs:
        if old not in content:
            raise SystemExit(f"Expected text not found in {path}: {old}")
        content = content.replace(old, new)

    path.write_text(content, encoding="utf-8")
PY

cat > database/migrations/versions/0004_adjust_audio_job_fade_defaults.py <<'EOF'
"""adjust audio job fade defaults

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "audio_jobs",
        "fade_in_seconds",
        existing_type=sa.Float(),
        server_default=sa.text("0.1"),
        existing_nullable=False,
    )
    op.alter_column(
        "audio_jobs",
        "fade_out_seconds",
        existing_type=sa.Float(),
        server_default=sa.text("0.1"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "audio_jobs",
        "fade_in_seconds",
        existing_type=sa.Float(),
        server_default=sa.text("1.0"),
        existing_nullable=False,
    )
    op.alter_column(
        "audio_jobs",
        "fade_out_seconds",
        existing_type=sa.Float(),
        server_default=sa.text("1.0"),
        existing_nullable=False,
    )
EOF

cat > apps/api/tests/test_audio_short_clip_defaults.py <<'EOF'
from app.schemas.audio import AudioGenerationRequest


def test_one_second_clip_accepts_default_fades() -> None:
    request = AudioGenerationRequest(
        title="One Second Tone",
        frequency_hz=432,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
    )

    assert request.fade_in_seconds == 0.1
    assert request.fade_out_seconds == 0.1
EOF

echo "Update 008A applied successfully."
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
