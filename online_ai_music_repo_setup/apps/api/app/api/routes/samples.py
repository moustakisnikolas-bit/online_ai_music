from dataclasses import asdict

import httpx
from fastapi import APIRouter, HTTPException, status

from app.audio.sample_library import (
    SAMPLE_LIBRARY_DIR,
    NaturalSoundSample,
    get_sample,
    list_samples,
    register_sample,
    resolve_sample_audio_path,
)
from app.core.config import get_settings
from app.schemas.instrumental import InstrumentalGenerationRequest
from app.schemas.sample import NaturalSoundSampleResponse
from app.services.instrumental_generator import generate_instrumental_clip

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


@router.post("/generate", response_model=NaturalSoundSampleResponse)
def generate_instrumental_sample(
    payload: InstrumentalGenerationRequest,
) -> NaturalSoundSampleResponse:
    filename = f"{payload.sample_id}.wav"
    output_path = SAMPLE_LIBRARY_DIR / filename

    try:
        generate_instrumental_clip(
            payload.prompt,
            duration_seconds=payload.duration_seconds,
            output_path=output_path,
            seed=payload.seed,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (RuntimeError, TimeoutError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Instrumental generation failed: {exc}",
        ) from exc

    sample = NaturalSoundSample(
        id=payload.sample_id,
        label=payload.label,
        category=payload.category,
        filename=filename,
        license=(
            "Stable Audio Open (Stability AI Community License -- free for "
            "commercial use under $1M/yr annual revenue)"
        ),
        source_url=None,
        attribution=f"Generated via {get_settings().stable_audio_model}, prompt: {payload.prompt!r}",
        source_type="ai_generated",
    )

    try:
        register_sample(sample)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return NaturalSoundSampleResponse(**asdict(sample), available=True)
