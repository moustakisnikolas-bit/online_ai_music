import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
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
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
