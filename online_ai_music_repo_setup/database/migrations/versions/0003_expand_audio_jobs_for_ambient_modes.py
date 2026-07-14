"""expand audio jobs for ambient modes

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audio_jobs",
        sa.Column("mode", sa.String(length=50), nullable=False, server_default="sine"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("layers", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("preset_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("fade_in_seconds", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("fade_out_seconds", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("seed", sa.Integer(), nullable=True),
    )
    op.alter_column("audio_jobs", "frequency_hz", nullable=True)


def downgrade() -> None:
    op.alter_column("audio_jobs", "frequency_hz", nullable=False)
    op.drop_column("audio_jobs", "seed")
    op.drop_column("audio_jobs", "fade_out_seconds")
    op.drop_column("audio_jobs", "fade_in_seconds")
    op.drop_column("audio_jobs", "preset_name")
    op.drop_column("audio_jobs", "layers")
    op.drop_column("audio_jobs", "mode")
