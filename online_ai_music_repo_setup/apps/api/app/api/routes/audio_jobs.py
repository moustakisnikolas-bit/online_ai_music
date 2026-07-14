import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.repositories.audio_jobs import create_audio_job, get_audio_job, list_audio_jobs
from app.schemas.audio_job import AudioJobCreate, AudioJobResponse
from app.services.audio_queue import enqueue_audio_job

router = APIRouter(prefix="/audio/jobs", tags=["audio-jobs"])


@router.post("", response_model=AudioJobResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_audio_job(
    payload: AudioJobCreate,
    db: Session = Depends(get_db),
) -> AudioJobResponse:
    job = create_audio_job(db, payload)

    try:
        enqueue_audio_job(job.id)
    except Exception as exc:
        job.status = "queue_failed"
        job.error_message = str(exc)
        db.commit()
        db.refresh(job)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The audio job could not be queued.",
        ) from exc

    return job


@router.get("/{job_id}", response_model=AudioJobResponse)
def get_audio_job_endpoint(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AudioJobResponse:
    job = get_audio_job(db, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio job not found.",
        )

    return job


@router.get("", response_model=list[AudioJobResponse])
def list_audio_jobs_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AudioJobResponse]:
    return list_audio_jobs(db, limit=limit)
