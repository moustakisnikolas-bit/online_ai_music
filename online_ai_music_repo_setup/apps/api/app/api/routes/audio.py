from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse
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
