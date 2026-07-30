import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class YouTubeCredential(Base):
    """
    A connected YouTube channel's OAuth tokens.

    AION is a single-operator MVP with no user/workspace model yet, so this
    is effectively a singleton table: one row per connected channel. It
    becomes per-workspace once a workspace concept exists.
    """

    __tablename__ = "youtube_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    channel_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    channel_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class YouTubePublication(Base):
    """A single upload attempt of an audio job's video package to YouTube."""

    __tablename__ = "youtube_publications"

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
    video_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="queued", index=True
    )
    youtube_video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Tracks whether a custom thumbnail was actually set, separate from the
    # video upload succeeding -- a thumbnail failure shouldn't fail the
    # whole publish (the video is already live), but silently swallowing it
    # would hide that YouTube is showing a random auto-picked frame instead
    # of the artwork.
    thumbnail_set: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class YouTubeQuotaUsage(Base):
    """Our own daily ledger of YouTube Data API v3 quota usage -- the API
    doesn't expose real-time remaining quota, so this is how the album
    pipeline's upload pacer knows how much room is left today. One row
    per Pacific-Time calendar day (quota resets at Pacific midnight).
    Every real YouTube write anywhere in the app -- not just album
    uploads -- must record its cost here, or the pacer will over-schedule
    relative to what's actually been spent.
    """

    __tablename__ = "youtube_quota_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    units_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
