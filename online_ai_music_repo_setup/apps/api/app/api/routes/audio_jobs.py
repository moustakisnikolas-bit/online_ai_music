import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.repositories.audio_jobs import (
    create_audio_job,
    delete_audio_job,
    get_audio_job,
    list_audio_jobs,
)
from app.schemas.audio_job import (
    AudioJobCreate,
    AudioJobResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    DeleteJobResponse,
)
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


def _delete_job_and_file(db: Session, job_id: uuid.UUID) -> bool:
    job = get_audio_job(db, job_id)

    if job is None:
        return False

    output_path = job.output_file_path
    deleted = delete_audio_job(db, job_id)

    if deleted and output_path:
        Path(output_path).unlink(missing_ok=True)

    return deleted


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_audio_jobs_endpoint(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
) -> BulkDeleteResponse:
    deleted_ids: list[uuid.UUID] = []
    not_found_ids: list[uuid.UUID] = []

    for job_id in payload.job_ids:
        if _delete_job_and_file(db, job_id):
            deleted_ids.append(job_id)
        else:
            not_found_ids.append(job_id)

    return BulkDeleteResponse(deleted_ids=deleted_ids, not_found_ids=not_found_ids)


@router.delete("/{job_id}", response_model=DeleteJobResponse)
def delete_audio_job_endpoint(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DeleteJobResponse:
    # Returns a small JSON body (not 204) so the web UI's shared
    # jsonRequest() helper -- which always calls response.json() -- works
    # for this endpoint the same way it does for every other one.
    if not _delete_job_and_file(db, job_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio job not found.",
        )

    return DeleteJobResponse()
