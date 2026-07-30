from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.core.config import get_settings
from app.repositories.audio_jobs import get_audio_job
from app.repositories.internet_archive import (
    create_internet_archive_publication,
    mark_publication_failed,
    mark_publication_uploaded,
)
from app.schemas.publishing import (
    InternetArchivePublicationResponse,
    InternetArchiveStatusResponse,
    InternetArchiveUploadRequest,
)
from app.services.internet_archive_publisher import (
    build_item_identifier,
    ensure_configured,
    upload_track,
)
from app.services.youtube_publisher import ensure_job_is_publishable

router = APIRouter(prefix="/publishing/internet-archive", tags=["publishing"])


# See exports.py's _audio_dir() for why this isn't a hardcoded constant:
# generated_audio_dir is a real, overridable Settings field, and this
# project's own .env points it outside the repo-relative default.
def _audio_dir() -> Path:
    return get_settings().audio_output_path


def _resolve_within(directory: Path, filename: str) -> Path | None:
    candidate = (directory / filename).resolve()

    if candidate.parent != directory.resolve() or not candidate.exists():
        return None

    return candidate


@router.get("/status", response_model=InternetArchiveStatusResponse)
def internet_archive_status(db: Session = Depends(get_db)) -> InternetArchiveStatusResponse:
    try:
        ensure_configured(db)
    except ValueError:
        return InternetArchiveStatusResponse(configured=False)

    return InternetArchiveStatusResponse(configured=True)


@router.post("/uploads", response_model=InternetArchivePublicationResponse)
def upload_to_internet_archive(
    payload: InternetArchiveUploadRequest,
    db: Session = Depends(get_db),
) -> InternetArchivePublicationResponse:
    job = get_audio_job(db, payload.audio_job_id)

    try:
        job = ensure_job_is_publishable(job)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    try:
        access_key, secret_key = ensure_configured(db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    audio_path = _resolve_within(_audio_dir(), payload.audio_filename)

    if audio_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found.",
        )

    item_identifier = build_item_identifier(payload.title, job.id)

    publication = create_internet_archive_publication(
        db,
        audio_job_id=job.id,
        item_identifier=item_identifier,
        audio_filename=payload.audio_filename,
        title=payload.title,
    )

    try:
        archive_url = upload_track(
            access_key=access_key,
            secret_key=secret_key,
            item_identifier=item_identifier,
            audio_path=audio_path,
            title=payload.title,
            description=payload.description,
            creator=payload.creator,
            license_url=payload.license_url,
        )
    except Exception as exc:
        publication = mark_publication_failed(db, publication, error_message=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Internet Archive upload failed: {exc}",
        ) from exc

    return mark_publication_uploaded(db, publication, archive_url=archive_url)
