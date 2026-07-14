import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.models.audio_job import AudioJob
from app.schemas.catalog import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)

router = APIRouter(prefix="/audio/jobs", tags=["review"])


def _get_job(db: Session, job_id: uuid.UUID) -> AudioJob:
    job = db.get(AudioJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio job not found.",
        )

    return job


@router.post(
    "/{job_id}/approve",
    response_model=ReviewDecisionResponse,
)
def approve_audio_job(
    job_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
) -> ReviewDecisionResponse:
    job = _get_job(db, job_id)

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed jobs can be approved.",
        )

    job.review_status = "approved"
    job.review_reason = payload.reason
    db.commit()

    return ReviewDecisionResponse(
        job_id=job.id,
        review_status=job.review_status,
        reason=job.review_reason,
    )


@router.post(
    "/{job_id}/reject",
    response_model=ReviewDecisionResponse,
)
def reject_audio_job(
    job_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
) -> ReviewDecisionResponse:
    job = _get_job(db, job_id)

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed jobs can be rejected.",
        )

    job.review_status = "rejected"
    job.review_reason = payload.reason
    db.commit()

    return ReviewDecisionResponse(
        job_id=job.id,
        review_status=job.review_status,
        reason=job.review_reason,
    )
