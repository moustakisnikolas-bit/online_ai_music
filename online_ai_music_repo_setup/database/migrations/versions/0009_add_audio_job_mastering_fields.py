"""add audio job mastering fields

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audio_jobs",
        sa.Column("loudness_lufs", sa.Float(), nullable=True),
    )
    op.add_column(
        "audio_jobs",
        sa.Column(
            "validation_warnings",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("audio_jobs", "validation_warnings")
    op.drop_column("audio_jobs", "loudness_lufs")
