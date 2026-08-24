"""add concept research

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "concept_research",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("concept_id", sa.String(length=50), nullable=False),
        sa.Column("query", sa.String(length=255), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("top_hz_values", sa.JSON(), nullable=False),
        sa.Column("top_noise_types", sa.JSON(), nullable=False),
        sa.Column("top_themes", sa.JSON(), nullable=False),
        sa.Column("top_videos", sa.JSON(), nullable=False),
        sa.Column(
            "researched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_concept_research_concept_id",
        "concept_research",
        ["concept_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_concept_research_concept_id", table_name="concept_research")
    op.drop_table("concept_research")
