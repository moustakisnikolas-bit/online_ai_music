import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.track_rating import TrackRating
from app.schemas.track_rating import TrackRatingCreate


def create_rating(
    db: Session,
    *,
    audio_job_id: uuid.UUID,
    payload: TrackRatingCreate,
) -> TrackRating:
    rating = TrackRating(
        audio_job_id=audio_job_id,
        stress_before=payload.stress_before,
        stress_after=payload.stress_after,
        mood_before=payload.mood_before,
        mood_after=payload.mood_after,
        sleep_onset_minutes=payload.sleep_onset_minutes,
        completed_listen=payload.completed_listen,
        skipped_at_seconds=payload.skipped_at_seconds,
        preferred_instruments=payload.preferred_instruments,
        uncomfortable_sounds=payload.uncomfortable_sounds,
        notes=payload.notes,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


def list_ratings_for_job(db: Session, audio_job_id: uuid.UUID) -> list[TrackRating]:
    statement = (
        select(TrackRating)
        .where(TrackRating.audio_job_id == audio_job_id)
        .order_by(TrackRating.created_at.desc())
    )
    return list(db.scalars(statement))
