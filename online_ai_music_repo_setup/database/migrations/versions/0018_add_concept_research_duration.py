"""add concept research duration buckets

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "concept_research",
        sa.Column("top_duration_buckets", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.alter_column("concept_research", "top_duration_buckets", server_default=None)


def downgrade() -> None:
    op.drop_column("concept_research", "top_duration_buckets")
