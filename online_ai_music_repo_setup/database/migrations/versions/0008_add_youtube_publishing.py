"""add youtube publishing tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "youtube_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("channel_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("channel_title", sa.String(length=255), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "youtube_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audio_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audio_jobs.id"),
            nullable=False,
        ),
        sa.Column("video_filename", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("youtube_video_id", sa.String(length=64), nullable=True),
        sa.Column("youtube_url", sa.String(length=512), nullable=True),
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
        "ix_youtube_publications_audio_job_id",
        "youtube_publications",
        ["audio_job_id"],
    )
    op.create_index(
        "ix_youtube_publications_status",
        "youtube_publications",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_youtube_publications_status",
        table_name="youtube_publications",
    )
    op.drop_index(
        "ix_youtube_publications_audio_job_id",
        table_name="youtube_publications",
    )
    op.drop_table("youtube_publications")
    op.drop_table("youtube_credentials")
