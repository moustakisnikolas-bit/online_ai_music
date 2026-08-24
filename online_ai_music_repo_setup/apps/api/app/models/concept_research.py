import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConceptResearch(Base):
    """Cached real-world competitive research for one concept: top Hz
    values, noise/sound types, and theme keywords seen among the
    highest-viewed real YouTube videos for that concept's niche.

    One row per concept_id (upserted on each fresh research run) --
    real YouTube Data API search results, not estimated or fabricated,
    persisted so the Albums UI can display them without a live API call
    (and its real quota cost) on every page load.
    """

    __tablename__ = "concept_research"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # References app.audio.concepts.CONCEPTS by id, same pattern as
    # AlbumBatch.concept_id -- catalog is code, not a table.
    concept_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # [[value, count], ...] ordered most-to-least common -- a plain dict
    # would lose that ordering once round-tripped through JSON.
    top_hz_values: Mapped[list] = mapped_column(JSON, nullable=False)
    top_noise_types: Mapped[list] = mapped_column(JSON, nullable=False)
    top_themes: Mapped[list] = mapped_column(JSON, nullable=False)
    # Real video length, bucketed (e.g. "3-6hr") -- from the same
    # search results, parsed from contentDetails.duration (ISO 8601)
    # which earlier research fetched but never analyzed.
    top_duration_buckets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    top_videos: Mapped[list] = mapped_column(JSON, nullable=False)
    researched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
