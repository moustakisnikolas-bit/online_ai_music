import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.repositories.audio_jobs import get_audio_job
from app.repositories.track_ratings import create_rating, list_ratings_for_job
from app.schemas.track_rating import TrackRatingCreate, TrackRatingResponse

router = APIRouter(prefix="/audio/jobs", tags=["track-ratings"])


def _get_job_or_404(db: Session, job_id: uuid.UUID):
    job = get_audio_job(db, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio job not found.",
        )

    return job


@router.post(
    "/{job_id}/ratings",
    response_model=TrackRatingResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_track_rating(
    job_id: uuid.UUID,
    payload: TrackRatingCreate,
    db: Session = Depends(get_db),
) -> TrackRatingResponse:
    _get_job_or_404(db, job_id)
    return create_rating(db, audio_job_id=job_id, payload=payload)


@router.get(
    "/{job_id}/ratings",
    response_model=list[TrackRatingResponse],
)
def list_track_ratings(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[TrackRatingResponse]:
    _get_job_or_404(db, job_id)
    return list_ratings_for_job(db, job_id)
