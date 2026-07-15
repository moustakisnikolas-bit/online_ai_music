from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.core.config import get_settings
from app.repositories.audio_jobs import create_completed_audio_job
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse
from app.schemas.audio_job import AudioJobResponse
from app.services.audio_generator import generate_audio

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/generate", response_model=AudioGenerationResponse)
def generate_audio_endpoint(
    request: AudioGenerationRequest,
) -> AudioGenerationResponse:
    settings = get_settings()

    try:
        return generate_audio(
            request=request,
            output_dir=settings.audio_output_path,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Audio generation failed: {exc}",
        ) from exc


@router.post("/generate-and-catalog", response_model=AudioJobResponse)
def generate_and_catalog_audio_endpoint(
    request: AudioGenerationRequest,
    db: Session = Depends(get_db),
) -> AudioJobResponse:
    # Same synchronous generation as /generate, but also persists a
    # completed AudioJob row so the result is reviewable and publishable
    # instead of only existing as a file on disk.
    settings = get_settings()

    try:
        result = generate_audio(
            request=request,
            output_dir=settings.audio_output_path,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Audio generation failed: {exc}",
        ) from exc

    return create_completed_audio_job(db, request=request, response=result)
