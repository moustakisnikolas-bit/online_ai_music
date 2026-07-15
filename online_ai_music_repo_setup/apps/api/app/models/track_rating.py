import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrackRating(Base):
    """
    Before/after outcome data for a listened-to track (production spec
    section 9: personalization). Enables evidence-informed personalization
    without presenting the system as a medical diagnostic tool -- these
    are self-reported ratings, not clinical measurements.
    """

    __tablename__ = "track_ratings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    audio_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audio_jobs.id"),
        nullable=False,
        index=True,
    )
    stress_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mood_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mood_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_onset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_listen: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    skipped_at_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_instruments: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    uncomfortable_sounds: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
