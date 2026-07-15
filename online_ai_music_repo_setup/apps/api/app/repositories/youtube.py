import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.youtube_publishing import YouTubeCredential, YouTubePublication


def get_youtube_credential(db: Session) -> YouTubeCredential | None:
    statement = select(YouTubeCredential).order_by(
        YouTubeCredential.connected_at.desc()
    )
    return db.scalars(statement).first()


def upsert_youtube_credential(
    db: Session,
    *,
    channel_id: str,
    channel_title: str | None,
    access_token: str,
    refresh_token: str,
    token_expiry: datetime | None,
    scopes: list[str],
) -> YouTubeCredential:
    credential = db.scalars(
        select(YouTubeCredential).where(YouTubeCredential.channel_id == channel_id)
    ).first()

    if credential is None:
        credential = YouTubeCredential(channel_id=channel_id)
        db.add(credential)

    credential.channel_title = channel_title
    credential.access_token = access_token
    credential.refresh_token = refresh_token
    credential.token_expiry = token_expiry
    credential.scopes = scopes

    db.commit()
    db.refresh(credential)
    return credential


def create_youtube_publication(
    db: Session,
    *,
    audio_job_id: uuid.UUID,
    video_filename: str,
    title: str,
) -> YouTubePublication:
    publication = YouTubePublication(
        audio_job_id=audio_job_id,
        video_filename=video_filename,
        title=title,
        status="queued",
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return publication


def mark_publication_uploaded(
    db: Session,
    publication: YouTubePublication,
    *,
    youtube_video_id: str,
    youtube_url: str,
) -> YouTubePublication:
    publication.status = "uploaded"
    publication.youtube_video_id = youtube_video_id
    publication.youtube_url = youtube_url
    publication.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(publication)
    return publication


def mark_publication_failed(
    db: Session,
    publication: YouTubePublication,
    *,
    error_message: str,
) -> YouTubePublication:
    publication.status = "failed"
    publication.error_message = error_message
    publication.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(publication)
    return publication
