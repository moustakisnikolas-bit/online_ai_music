from fastapi import APIRouter

from app.audio.sample_library import (
    SAMPLE_LIBRARY_DIR,
    get_sample,
    list_samples,
    resolve_sample_audio_path,
)
from app.schemas.sample import NaturalSoundSampleResponse

router = APIRouter(prefix="/audio/samples", tags=["audio-samples"])


@router.get("", response_model=list[NaturalSoundSampleResponse])
def list_natural_sound_samples() -> list[NaturalSoundSampleResponse]:
    responses = []

    for entry in list_samples():
        sample = get_sample(entry["id"])

        try:
            resolve_sample_audio_path(sample, SAMPLE_LIBRARY_DIR)
            available = True
        except (ValueError, FileNotFoundError):
            available = False

        responses.append(NaturalSoundSampleResponse(**entry, available=available))

    return responses
