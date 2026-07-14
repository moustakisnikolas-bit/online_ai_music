from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse
from app.services.audio_generator import generate_sine_wave

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/generate", response_model=AudioGenerationResponse)
def generate_audio(request: AudioGenerationRequest) -> AudioGenerationResponse:
    settings = get_settings()

    try:
        return generate_sine_wave(
            request=request,
            output_dir=settings.audio_output_path,
        )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Audio generation failed: {exc}",
        ) from exc
