"""add album pipeline tables

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "album_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("concept_id", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("youtube_playlist_id", sa.String(length=64), nullable=True),
        sa.Column("youtube_playlist_url", sa.String(length=512), nullable=True),
        sa.Column(
            "playlist_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_album_batches_concept_id", "album_batches", ["concept_id"]
    )
    op.create_index(
        "ix_album_batches_status", "album_batches", ["status"]
    )

    op.create_table(
        "album_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "album_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("album_batches.id"),
            nullable=False,
        ),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("combination", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "harmony_check_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "harmony_check_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("harmony_check_report", sa.JSON(), nullable=True),
        sa.Column(
            "audio_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audio_jobs.id"),
            nullable=True,
        ),
        sa.Column("video_filename", sa.String(length=255), nullable=True),
        sa.Column("artwork_filename", sa.String(length=255), nullable=True),
        sa.Column(
            "youtube_publication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("youtube_publications.id"),
            nullable=True,
        ),
        sa.Column("scheduled_upload_date", sa.Date(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "playlist_item_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_album_tracks_album_batch_id", "album_tracks", ["album_batch_id"]
    )
    op.create_index(
        "ix_album_tracks_status", "album_tracks", ["status"]
    )

    op.create_table(
        "youtube_quota_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usage_date", sa.Date(), nullable=False, unique=True),
        sa.Column(
            "units_used",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("youtube_quota_usage")
    op.drop_index("ix_album_tracks_status", table_name="album_tracks")
    op.drop_index("ix_album_tracks_album_batch_id", table_name="album_tracks")
    op.drop_table("album_tracks")
    op.drop_index("ix_album_batches_status", table_name="album_batches")
    op.drop_index("ix_album_batches_concept_id", table_name="album_batches")
    op.drop_table("album_batches")
