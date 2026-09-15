"""add album track shorts

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "youtube_publications",
        sa.Column("video_kind", sa.String(length=16), nullable=False, server_default="long"),
    )
    op.alter_column("youtube_publications", "video_kind", server_default=None)

    op.create_table(
        "album_track_shorts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "album_track_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("album_tracks.id"),
            nullable=False,
        ),
        sa.Column("clip_index", sa.Integer(), nullable=False),
        sa.Column("start_offset_seconds", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
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
        sa.UniqueConstraint("album_track_id", "clip_index", name="uq_album_track_shorts_track_clip"),
    )
    op.create_index(
        "ix_album_track_shorts_album_track_id", "album_track_shorts", ["album_track_id"]
    )
    op.create_index(
        "ix_album_track_shorts_status", "album_track_shorts", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_album_track_shorts_status", table_name="album_track_shorts")
    op.drop_index("ix_album_track_shorts_album_track_id", table_name="album_track_shorts")
    op.drop_table("album_track_shorts")
    op.drop_column("youtube_publications", "video_kind")
