"""add track ratings

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "track_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audio_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audio_jobs.id"),
            nullable=False,
        ),
        sa.Column("stress_before", sa.Integer(), nullable=True),
        sa.Column("stress_after", sa.Integer(), nullable=True),
        sa.Column("mood_before", sa.Integer(), nullable=True),
        sa.Column("mood_after", sa.Integer(), nullable=True),
        sa.Column("sleep_onset_minutes", sa.Integer(), nullable=True),
        sa.Column("completed_listen", sa.Boolean(), nullable=True),
        sa.Column("skipped_at_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "preferred_instruments",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "uncomfortable_sounds",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_track_ratings_audio_job_id",
        "track_ratings",
        ["audio_job_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_track_ratings_audio_job_id",
        table_name="track_ratings",
    )
    op.drop_table("track_ratings")
