import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.internet_archive_publishing import InternetArchivePublication


def create_internet_archive_publication(
    db: Session,
    *,
    audio_job_id: uuid.UUID,
    item_identifier: str,
    audio_filename: str,
    title: str,
) -> InternetArchivePublication:
    publication = InternetArchivePublication(
        audio_job_id=audio_job_id,
        item_identifier=item_identifier,
        audio_filename=audio_filename,
        title=title,
        status="queued",
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return publication


def mark_publication_uploaded(
    db: Session,
    publication: InternetArchivePublication,
    *,
    archive_url: str,
) -> InternetArchivePublication:
    publication.status = "uploaded"
    publication.archive_url = archive_url
    publication.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(publication)
    return publication


def mark_publication_failed(
    db: Session,
    publication: InternetArchivePublication,
    *,
    error_message: str,
) -> InternetArchivePublication:
    publication.status = "failed"
    publication.error_message = error_message
    publication.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(publication)
    return publication
