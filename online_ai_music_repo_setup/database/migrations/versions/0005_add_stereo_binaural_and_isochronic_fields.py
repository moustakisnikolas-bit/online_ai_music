"""add stereo binaural and isochronic fields

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audio_jobs",
        sa.Column("channels", sa.String(length=20), nullable=False, server_default="mono"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("left_frequency_hz", sa.Float(), nullable=True),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("right_frequency_hz", sa.Float(), nullable=True),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("pulse_frequency_hz", sa.Float(), nullable=True),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("modulation_depth", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("seamless_loop", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "audio_jobs",
        sa.Column("loop_crossfade_seconds", sa.Float(), nullable=False, server_default="0.25"),
    )


def downgrade() -> None:
    op.drop_column("audio_jobs", "loop_crossfade_seconds")
    op.drop_column("audio_jobs", "seamless_loop")
    op.drop_column("audio_jobs", "modulation_depth")
    op.drop_column("audio_jobs", "pulse_frequency_hz")
    op.drop_column("audio_jobs", "right_frequency_hz")
    op.drop_column("audio_jobs", "left_frequency_hz")
    op.drop_column("audio_jobs", "channels")
