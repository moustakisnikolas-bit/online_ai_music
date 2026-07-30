"""add internet archive publishing table

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "internet_archive_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audio_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audio_jobs.id"),
            nullable=False,
        ),
        sa.Column("item_identifier", sa.String(length=100), nullable=False),
        sa.Column("audio_filename", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("archive_url", sa.String(length=512), nullable=True),
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
        "ix_internet_archive_publications_audio_job_id",
        "internet_archive_publications",
        ["audio_job_id"],
    )
    op.create_index(
        "ix_internet_archive_publications_status",
        "internet_archive_publications",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_internet_archive_publications_status",
        table_name="internet_archive_publications",
    )
    op.drop_index(
        "ix_internet_archive_publications_audio_job_id",
        table_name="internet_archive_publications",
    )
    op.drop_table("internet_archive_publications")
