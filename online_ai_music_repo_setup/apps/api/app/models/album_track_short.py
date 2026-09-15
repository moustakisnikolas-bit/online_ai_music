import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlbumTrackShort(Base):
    """One YouTube Shorts clip cut from a confirmed-uploaded AlbumTrack's
    own audio -- see app/services/shorts_pipeline.py. Reuses
    YouTubePublication for upload status/video id (via
    youtube_publication_id), the same way AlbumTrack itself does, rather
    than duplicating that bookkeeping a second time.
    """

    __tablename__ = "album_track_shorts"
    __table_args__ = (
        UniqueConstraint("album_track_id", "clip_index", name="uq_album_track_shorts_track_clip"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    album_track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("album_tracks.id"),
        nullable=False,
        index=True,
    )
    # 0..settings.shorts_per_track-1 -- which spread-out segment of the
    # parent track's audio this clip is.
    clip_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )
    video_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artwork_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    youtube_publication_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("youtube_publications.id"), nullable=True
    )
    # Same purpose and mechanism as AlbumTrack.scheduled_upload_date: when
    # the upload stage finds quota insufficient, it pushes this to
    # tomorrow rather than failing, and list_actionable_track_shorts
    # excludes shorts with a future date here -- without it, one
    # quota-blocked "rendered" short would keep winning the FIFO ordering
    # every tick and starve every other short (including ones that only
    # need a render, not quota) until quota resets.
    scheduled_upload_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
