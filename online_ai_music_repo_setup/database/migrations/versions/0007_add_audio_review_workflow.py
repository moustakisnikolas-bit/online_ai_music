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
