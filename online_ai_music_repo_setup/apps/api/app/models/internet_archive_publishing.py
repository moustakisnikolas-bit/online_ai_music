import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InternetArchivePublication(Base):
    """A single upload attempt of an audio job's audio to the Internet
    Archive.

    Unlike YouTube, there's no per-connection OAuth credential to store --
    Internet Archive's S3-like API auths with a static access/secret key
    pair (see app_secrets: internet_archive_access_key /
    internet_archive_secret_key), so this table only tracks publish
    attempts, mirroring YouTubePublication's shape for a consistent
    publish-history UX.
    """

    __tablename__ = "internet_archive_publications"

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
    item_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    audio_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="queued", index=True
    )
    archive_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
