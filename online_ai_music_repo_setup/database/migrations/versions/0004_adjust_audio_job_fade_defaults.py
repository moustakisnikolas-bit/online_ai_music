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
