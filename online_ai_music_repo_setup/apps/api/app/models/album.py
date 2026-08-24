import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlbumBatch(Base):
    """A concept-driven batch of tracks (count set by
    album_pipeline.TRACKS_PER_ALBUM) published as one YouTube Playlist
    ("album"). See app/services/album_pipeline.py for the orchestration
    that drives this through its stages.
    """

    __tablename__ = "album_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # References app.audio.concepts.CONCEPTS by id -- catalog is code, not
    # a table, same pattern as PurposeProfile.id today.
    concept_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft", index=True
    )
    youtube_playlist_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    youtube_playlist_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    playlist_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AlbumTrack(Base):
    """One of an AlbumBatch's tracks, advancing through the pipeline
    state machine documented in album_pipeline.py.
    """

    __tablename__ = "album_tracks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    album_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("album_batches.id"),
        nullable=False,
        index=True,
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # A serialized TrackCombination -- see
    # app/services/album_combinations.py's TrackCombination -- stored so a
    # retry/resume after a worker restart doesn't need to regenerate it.
    combination: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )
    harmony_check_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    harmony_check_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    harmony_check_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audio_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audio_jobs.id"), nullable=True
    )
    video_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artwork_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Reuses the existing YouTubePublication row/state rather than
    # duplicating upload status tracking a second time.
    youtube_publication_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("youtube_publications.id"), nullable=True
    )
    scheduled_upload_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    playlist_item_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
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
